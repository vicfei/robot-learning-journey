"""蒸馏打标 step2：动作映射（累积式）+ 蒸馏数据集构建（robotics venv 运行）。

映射方案（已与用户对齐）: 累积式闭环轨迹
    a[0] = state_true[0]                      # episode 起点锚定
    a[t] = clip(a[t-1] + diag(k)·M·(Δx,Δy)_teacher[t], 0, 512)
    M: 轴排列+符号（probe 时由相关性一次性选定, 之后冻结）
    k: 统计标定 k_j = std(真值增量_j) / std(M·d)_j（probe 批上算, 之后冻结）

用法:
    venv/bin/python distill/step2_build_dataset.py --probe   # 10 帧映射验证报告
    venv/bin/python distill/step2_build_dataset.py           # 全量 -> data/pusht_distill
"""
import os, json, argparse
import numpy as np
import torch

ROOT = os.path.expanduser("~/services/robotics")
DISTILL = os.path.join(ROOT, "distill")
MAP_CFG = os.path.join(DISTILL, "map_config.json")
TASK = "Push the T-shaped block onto the T-shaped target."

from lerobot.datasets.lerobot_dataset import LeRobotDataset


def load_aligned(n_limit=0):
    """按 manifest 顺序取 teacher 动作 + 原数据集对应帧真值。"""
    manifest = json.load(open(os.path.join(DISTILL, "manifest.json")))
    z = np.load(os.path.join(DISTILL, "teacher_actions.npz"), allow_pickle=True)
    by_file = {f: a for f, a in zip(z["files"].tolist(), z["actions"])}
    rows = [(m, by_file[m["file"]]) for m in manifest if m["file"] in by_file]
    if n_limit:
        rows = rows[:n_limit]
    ds = LeRobotDataset("lerobot/pusht", root=f"{ROOT}/data/pusht", video_backend="pyav")
    gt_actions, gt_states, imgs = [], [], []
    for m, _ in rows:
        f = ds[m["dataset_index"]]
        gt_actions.append(f["action"].numpy())
        gt_states.append(f["observation.state"].numpy())
        imgs.append(f["observation.image"])
    return ([r[0] for r in rows], np.stack([r[1] for r in rows]),
            np.stack(gt_actions), np.stack(gt_states), imgs, ds)


def pick_mapping(d, gt_delta):
    """teacher 增量 vs 真值增量的 2x2 相关矩阵 -> 最优轴排列+符号矩阵 M。"""
    C = np.corrcoef(np.stack([d[:, 0], d[:, 1], gt_delta[:, 0], gt_delta[:, 1]]))[:2, 2:]
    C = np.nan_to_num(C)
    i0, j0 = np.unravel_index(np.argmax(np.abs(C)), C.shape)
    i1, j1 = (1 - i0), (1 - j0)  # 剩余轴
    M = np.zeros((2, 2))
    M[j0, i0] = np.sign(C[i0, j0]) or 1.0   # M: teacher 轴 i -> 像素轴 j
    M[j1, i1] = np.sign(C[i1, j1]) or 1.0
    return C, M


def accumulate(d, M, k, a0):
    a = np.zeros((len(d) + 1, 2))
    a[0] = a0
    for t in range(len(d)):
        a[t + 1] = np.clip(a[t] + (M @ d[t]) * k, 0, 512)
    return a[1:]


def run_probe(n):
    manif, t_acts, gt_acts, gt_states, _, _ = load_aligned(n)
    print(f"== 映射 probe（{len(manif)} 帧, {len(set(m['episode_index'] for m in manif))} episodes）==\n")
    print("episode 0 前 10 帧 | teacher 7-DoF 原始输出")
    for i, (m, a) in enumerate(zip(manif, t_acts)):
        if m["episode_index"] != manif[0]["episode_index"] or i >= 10:
            break
        print(f"{m['frame_index']:4d} | {np.array2string(a, precision=4, floatmode='fixed')}")

    # 同 episode 相邻帧: teacher delta[t] 对应 gt[t+1]-gt[t]
    eps = np.array([m["episode_index"] for m in manif])
    same = eps[1:] == eps[:-1]
    d = t_acts[:-1, :2][same]
    gt_delta = np.diff(gt_acts, axis=0)[same]
    C, M = pick_mapping(d, gt_delta)
    print(f"\nteacher(Δx,Δy) vs 真值增量 相关系数矩阵:\n{np.array2string(C, precision=3)}")
    print(f"选定映射 M (teacher轴->像素轴):\n{np.array2string(M.astype(int))}")

    md = (M @ d.T).T
    k = gt_delta.std(0) / np.maximum(md.std(0), 1e-8)
    print(f"统计标定 scale k = {np.array2string(k, precision=1)} px/unit "
          f"(真值步长 std {np.array2string(gt_delta.std(0), precision=1)} px)")

    # 累积轨迹 vs 真值
    ep0 = manif[0]["episode_index"]
    n_ep0 = int((eps == ep0).sum())
    a_teach = accumulate(d[:n_ep0], M, k, gt_states[0])
    a_gt = gt_acts[:n_ep0]
    err = np.linalg.norm(a_teach - a_gt, axis=1)
    cos = (a_teach * a_gt).sum(1) / (np.linalg.norm(a_teach, axis=1) * np.linalg.norm(a_gt, axis=1) + 1e-9)
    ang = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    print(f"\n帧 | teacher动作(px)       | 真值动作(px)        | 偏差px | 角度差")
    for i in range(n_ep0):
        print(f"{manif[i]['frame_index']:4d} | ({a_teach[i,0]:6.1f},{a_teach[i,1]:6.1f}) | "
              f"({a_gt[i,0]:6.1f},{a_gt[i,1]:6.1f}) | {err[i]:6.1f} | {ang[i]:5.0f}°")
    print(f"\nL2 偏差: mean {err.mean():.1f}px median {np.median(err):.1f}px | "
          f"方向角差 median {np.median(ang):.0f}°")
    print(f"参照: 专家自身相邻步长 std ~9.5px; action-state 偏移 std ~20px")
    cfg = {"M": M.tolist(), "k": k.tolist(), "probe_frames": int(len(manif)),
           "corr_matrix": C.tolist()}
    json.dump(cfg, open(MAP_CFG, "w"), indent=1)
    print(f"\n映射参数已冻结 -> {MAP_CFG}")
    print(cfg)


def run_full():
    cfg = json.load(open(MAP_CFG))
    M, k = np.array(cfg["M"]), np.array(cfg["k"])
    manif, t_acts, gt_acts, gt_states, imgs, _ = load_aligned()
    print(f"全量: {len(manif)} 帧, 映射 M={M.astype(int).tolist()} k={k.round(1).tolist()}")

    out_root = f"{ROOT}/data/pusht_distill"
    # 注: shape 必须用 tuple —— lerobot 0.4.4 的 validate_feature_numpy_array 用
    # `value.shape != expected_shape` 比较, np.shape 是 tuple, list 声明会永远不等
    feats = {
        "observation.image": {"dtype": "video", "shape": (96, 96, 3),
                              "names": ["height", "width", "channel"]},
        "observation.state": {"dtype": "float32", "shape": (2,),
                              "names": {"motors": ["motor_0", "motor_1"]}},
        "action": {"dtype": "float32", "shape": (2,),
                   "names": {"motors": ["motor_0", "motor_1"]}},
    }
    out = LeRobotDataset.create(
        repo_id="pusht_distill", fps=10, root=out_root, features=feats,
        use_videos=True, video_backend="pyav",
    )
    from PIL import Image
    # 按 episode 分组累积
    from collections import defaultdict
    by_ep = defaultdict(list)
    for i, m in enumerate(manif):
        by_ep[m["episode_index"]].append(i)
    total_err = []
    for ep, idxs in sorted(by_ep.items()):
        d = t_acts[idxs, :2]
        a_teach = accumulate(d, M, k, gt_states[idxs[0]])
        for j, i in enumerate(idxs):
            img = Image.open(os.path.join(DISTILL, manif[i]["file"])).convert("RGB")
            out.add_frame({
                "observation.image": img,
                "observation.state": np.asarray(gt_states[i], dtype=np.float32),
                "action": np.asarray(a_teach[j], dtype=np.float32),
                "task": TASK,
            })
            total_err.append(np.linalg.norm(a_teach[j] - gt_acts[i]))
        out.save_episode()
        print(f"episode {ep}: {len(idxs)} 帧已写", flush=True)
    total_err = np.array(total_err)
    print(f"\n蒸馏数据集完成: {out_root}/pusht_distill")
    print(f"teacher 累积轨迹 vs 真值全程偏差: mean {total_err.mean():.1f}px "
          f"median {np.median(total_err):.1f}px")
    json.dump({"n_frames": int(len(total_err)),
               "err_mean": float(total_err.mean()),
               "err_median": float(np.median(total_err))},
              open(os.path.join(DISTILL, "distill_stats.json"), "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    run_probe(args.n) if args.probe else run_full()
