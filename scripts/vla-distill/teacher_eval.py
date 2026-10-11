"""Teacher(OpenVLA+累积映射) 评测：回放原专家数据集 episode 0/1，与专家真值动作对比。

协议与 eval_smolvla_pusht.py 完全对齐（同一考卷）: L2 误差 + 方向角差。
映射参数来自 step2 冻结的 map_config.json（训练/评测同源）。

用法（vla venv + gcc-env）:
    source ~/gcc-env.sh
    ~/services/vla/venv/bin/python teacher_eval.py
"""
import os, sys, json, time
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import numpy as np

DISTILL = os.path.expanduser("~/services/robotics/distill")
ROOT = os.path.expanduser("~/services/robotics")
TASK_PROMPT = "push the T-shaped block onto the T-shaped target"

# step0 已导出的评测帧目录（teacher 逐帧推理吃 png）
FRAMES_DIR = os.path.join(DISTILL, "eval_frames")


def load_manifest():
    return json.load(open(os.path.join(DISTILL, "eval_manifest.json")))


def load_model():
    from transformers import AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig
    import torch
    import transformers.modeling_utils as _mu
    _orig_dispatch = _mu.dispatch_model
    def _safe_dispatch(model, *a, **k):
        try:
            return _orig_dispatch(model, *a, **k)
        except ValueError:
            for _, buf in model.named_buffers():
                if buf.device.type == "cpu":
                    buf.data = buf.to("cuda")
            return model
    _mu.dispatch_model = _safe_dispatch
    processor = AutoProcessor.from_pretrained(
        os.path.expanduser("~/services/vla/models/openvla-7b"), trust_remote_code=True)
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = AutoModelForVision2Seq.from_pretrained(
        os.path.expanduser("~/services/vla/models/openvla-7b"),
        quantization_config=quant_cfg, low_cpu_mem_usage=True,
        trust_remote_code=True, device_map={'': 0})
    return processor, model


def main():
    cfg = json.load(open(os.path.join(DISTILL, "map_config.json")))
    M, k = np.array(cfg["M"]), np.array(cfg["k"])
    manifest = load_manifest()
    print(f"评测帧数: {len(manifest)} | M={M.astype(int).tolist()} k={k.round(1).tolist()}")

    processor, model = load_model()
    from PIL import Image
    import torch
    prompt = f"In: What action should the robot take to {TASK_PROMPT}?\nOut:"

    errs, angs = [], []
    ep_cur, a_acc = None, None
    for m in manifest:
        if m["episode_index"] != ep_cur:  # episode 边界 -> 重锚
            ep_cur = m["episode_index"]
            a_acc = np.array(m["state0"], dtype=np.float64)
        img = Image.open(os.path.join(DISTILL, m["file"])).convert("RGB")
        inputs = processor(prompt, img).to("cuda", dtype=torch.float16)
        with torch.inference_mode():
            act = model.predict_action(**inputs, unnorm_key="bridge_orig", do_sample=False)
        d = np.asarray(act, dtype=np.float64)[:2]
        a_acc = np.clip(a_acc + (M @ d) * k, 0, 512)
        g = np.array(m["gt_action"], dtype=np.float64)
        errs.append(np.linalg.norm(a_acc - g))
        cos = np.dot(a_acc, g) / (np.linalg.norm(a_acc) * np.linalg.norm(g) + 1e-9)
        angs.append(np.degrees(np.arccos(np.clip(cos, -1, 1))))

    errs, angs = np.array(errs), np.array(angs)
    print(f"\n[Teacher] 回放 {len(errs)} 帧 | L2 误差 mean {errs.mean():.3f} median {np.median(errs):.3f}")
    print(f"[Teacher] 方向误差 median {np.median(angs):.0f}deg | <15deg 占比 {(angs<15).mean()*100:.0f}%")
    json.dump({"err_mean": float(errs.mean()), "err_median": float(np.median(errs)),
               "ang_median": float(np.median(angs)),
               "frac_lt15deg": float((angs < 15).mean())},
              open(os.path.join(DISTILL, "teacher_eval.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
