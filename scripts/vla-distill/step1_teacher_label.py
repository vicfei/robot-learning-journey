"""蒸馏打标 step1：OpenVLA-7B 4-bit 批量打标（vla venv + source gcc-env.sh 运行）。

用法:
    source ~/gcc-env.sh
    ~/services/vla/venv/bin/python step1_teacher_label.py            # 全量（断点续跑）
    ~/services/vla/venv/bin/python step1_teacher_label.py --limit 10 # probe

输入: distill/frames/**/*.png + manifest.json
输出: distill/teacher_actions.npz  {files, actions(N,7), times}
  actions = [Δx, Δy, Δz, Δroll, Δpitch, Δyaw, gripper]（bridge_orig 反归一化，物理单位）
"""
import os, time, json, argparse
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import numpy as np

DISTILL = os.path.expanduser("~/services/robotics/distill")
MODEL = os.path.expanduser("~/services/vla/models/openvla-7b")
TASK = "push the T-shaped block onto the T-shaped target"
NPZ = os.path.join(DISTILL, "teacher_actions.npz")


def load_model():
    from transformers import AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig
    import torch
    # patch: 4-bit 模型已在量化时落到 GPU，accelerate 的 dispatch 再 .to() 会抛错——跳过并手动补搬 CPU buffer
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

    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForVision2Seq.from_pretrained(
        MODEL, quantization_config=quant_cfg, low_cpu_mem_usage=True,
        trust_remote_code=True, device_map={'': 0},
    )
    return processor, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只标前 N 帧（0=全部）")
    args = ap.parse_args()

    manifest = json.load(open(os.path.join(DISTILL, "manifest.json")))
    if args.limit:
        manifest = manifest[:args.limit]

    # 断点续跑：npz 全量载入内存，每 10 帧整体重写
    all_files, all_acts = [], []
    if os.path.exists(NPZ):
        z = np.load(NPZ, allow_pickle=True)
        all_files = list(z["files"])
        all_acts = [a for a in z["actions"]]
        print(f"续跑: 已有 {len(all_files)} 帧")
    done = set(all_files)

    from PIL import Image
    import torch
    processor, model = load_model()
    prompt = f"In: What action should the robot take to {TASK}?\nOut:"

    t_start, n_new = time.time(), 0
    for i, m in enumerate(manifest):
        rel = m["file"]
        if rel in done:
            continue
        img = Image.open(os.path.join(DISTILL, rel)).convert("RGB")
        inputs = processor(prompt, img).to("cuda", dtype=torch.float16)
        with torch.inference_mode():
            act = model.predict_action(**inputs, unnorm_key="bridge_orig", do_sample=False)
        all_files.append(rel)
        all_acts.append(np.asarray(act, dtype=np.float32))
        done.add(rel)
        n_new += 1
        if n_new % 10 == 0:
            np.savez(NPZ, files=np.array(all_files),
                     actions=np.stack(all_acts), times=np.zeros(len(all_files)))
            el = time.time() - t_start
            print(f"[{i+1}/{len(manifest)}] {el:.0f}s ({el/n_new:.2f}s/帧) "
                  f"last={np.array2string(all_acts[-1], precision=3)}", flush=True)
    np.savez(NPZ, files=np.array(all_files), actions=np.stack(all_acts),
             times=np.zeros(len(all_files)))
    acts = np.stack(all_acts)
    print(f"完成: 共 {len(all_files)} 帧 -> {NPZ}")
    print(f"动作统计: mean={np.array2string(acts.mean(0), precision=4)}")
    print(f"          std ={np.array2string(acts.std(0), precision=4)}")


if __name__ == "__main__":
    main()
