"""导出评测帧：原专家数据集 episode 0/1 全帧 png + 真值（供 teacher_eval.py 用）。

用法: cd ~/services/robotics && venv/bin/python distill/step0b_export_eval_frames.py
输出: distill/eval_frames/ep{E}/f{F}.png + distill/eval_manifest.json
  manifest 每条: {episode_index, frame_index, file, gt_action[2], state0[2](episode首帧state)}
"""
import os, json
import numpy as np

ROOT = os.path.expanduser("~/services/robotics")
DISTILL = os.path.join(ROOT, "distill")
OUT_DIR = os.path.join(DISTILL, "eval_frames")

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from PIL import Image


def main():
    ds = LeRobotDataset("lerobot/pusht", root=f"{ROOT}/data/pusht", video_backend="pyav")
    manifest = []
    state0 = {}
    for ep in (0, 1):
        idxs = [i for i in range(len(ds))
                if ds.meta  # noqa
                and ds[i]["episode_index"].item() == ep]
        ep_dir = os.path.join(OUT_DIR, f"ep{ep:03d}")
        os.makedirs(ep_dir, exist_ok=True)
        for di in idxs:
            f = ds[di]
            fi = f["frame_index"].item()
            state0.setdefault(ep, f["observation.state"].numpy())
            png = os.path.join(ep_dir, f"f{fi:05d}.png")
            img = f["observation.image"]
            Image.fromarray((img.permute(1, 2, 0).numpy() * 255).astype(np.uint8)).save(png)
            manifest.append({
                "episode_index": ep, "frame_index": fi,
                "file": os.path.relpath(png, DISTILL),
                "gt_action": f["action"].numpy().tolist(),
                "state0": state0[ep].tolist(),
            })
        print(f"episode {ep}: {len(idxs)} 帧")
    json.dump(manifest, open(os.path.join(DISTILL, "eval_manifest.json"), "w"), indent=1)
    print(f"共 {len(manifest)} 帧 -> eval_manifest.json")


if __name__ == "__main__":
    main()
