"""蒸馏打标 step0：从 pusht 数据集抽 episode 帧解码为 png（robotics venv 运行）。

用法:
    cd ~/services/robotics && venv/bin/python distill/step0_extract_frames.py --episodes 0-33
    ... --probe   # 只抽 episode 0 前 10 帧（映射试跑用）

输出:
    distill/frames/ep{E:03d}/f{F:05d}.png   96x96 RGB
    distill/manifest.json                    [{episode_index, frame_index, dataset_index, file}]
"""
import os, json, argparse
import torch

ROOT = os.path.expanduser("~/services/robotics")
OUT = os.path.join(ROOT, "distill")
FRAMES_DIR = os.path.join(OUT, "frames")

from lerobot.datasets.lerobot_dataset import LeRobotDataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="0-33")
    ap.add_argument("--probe", action="store_true", help="只抽 episode 0 前 10 帧")
    args = ap.parse_args()

    lo, hi = (int(x) for x in args.episodes.split("-"))
    eps = list(range(lo, hi + 1))

    ds = LeRobotDataset("lerobot/pusht", root=f"{ROOT}/data/pusht", video_backend="pyav")
    # 用 parquet 直读 episode_index 列（快）
    import pyarrow.parquet as pq
    import glob
    ep_list = []
    for f in sorted(glob.glob(f"{ROOT}/data/pusht/data/chunk-*/file-*.parquet")):
        ep_list.extend(pq.read_table(f, columns=["episode_index"]).to_pydict()["episode_index"])
    ep_list = [e if isinstance(e, int) else e[0] for e in ep_list]

    manifest = []
    limit = 10 if args.probe else None
    for ep in eps:
        idxs = [i for i, e in enumerate(ep_list) if e == ep]
        if not idxs:
            print(f"episode {ep}: 不存在，跳过")
            continue
        if limit:
            idxs = idxs[:limit]
        ep_dir = os.path.join(FRAMES_DIR, f"ep{ep:03d}")
        os.makedirs(ep_dir, exist_ok=True)
        from PIL import Image
        import numpy as np
        for di in idxs:
            frame = ds[di]
            fi = frame["frame_index"].item()
            img = frame["observation.image"]  # (3,96,96) float32 CHW, [0,1]
            png = os.path.join(ep_dir, f"f{fi:05d}.png")
            Image.fromarray((img.permute(1, 2, 0).numpy() * 255).astype(np.uint8)).save(png)
            manifest.append({
                "episode_index": ep, "frame_index": fi, "dataset_index": di,
                "file": os.path.relpath(png, OUT),
            })
        print(f"episode {ep}: {len(idxs)} 帧 -> {ep_dir}")

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"共 {len(manifest)} 帧, manifest 已写 {OUT}/manifest.json")


if __name__ == "__main__":
    main()
