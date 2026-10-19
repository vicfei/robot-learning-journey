"""实验4第一档 · 程序专家 reach 采集器（SO-101 从臂, 度数语义, 校准后）

任务: 从 HOME 出发, reach 到 A/B/C 之一, 停留, 返回 HOME。
专家: 梯形速度插值(确定性)。30Hz 写目标 + 同步读实际位置。
记录: obs = 六关节实际度数 + 目标点 one-hot(3), action = 发送的六关节目标度数。
输出: reach_dataset.npz  (episodes: {obs(N,9), action(N,6), label})

用法:
  python expert_reach.py --demo          # 半幅慢速跑一条 A 轨迹(安全确认)
  python expert_reach.py --collect 48    # 正式采集 48 条(A/B/C 随机均衡)
"""
import os, sys, json, time, argparse
import numpy as np

sys.path.insert(0, os.path.expanduser("~/services/robotics"))

HOME = dict(shoulder_pan=0., shoulder_lift=-15., elbow_flex=-10., wrist_flex=0., wrist_roll=0., gripper=30.)
POINTS = {
    "A": dict(shoulder_pan=-25., shoulder_lift=-12., elbow_flex=-20., wrist_flex=0., wrist_roll=0., gripper=55.),
    "B": dict(shoulder_pan=25., shoulder_lift=-12., elbow_flex=-20., wrist_flex=0., wrist_roll=0., gripper=55.),
    "C": dict(shoulder_pan=0., shoulder_lift=5., elbow_flex=12., wrist_flex=-8., wrist_roll=0., gripper=55.),
}
MOTORS = list(HOME.keys())
HZ = 30


def make_bus():
    from lerobot.motors import Motor, MotorNormMode, MotorCalibration
    from lerobot.motors.feetech import FeetechMotorsBus
    cal = json.load(open(os.path.expanduser(
        "~/.cache/huggingface/lerobot/calibration/robots/so_follower/my_follower.json")))
    bus = FeetechMotorsBus(port="socket://192.168.208.1:9999", motors={
        "shoulder_pan": Motor(1, "sts3215", MotorNormMode.DEGREES),
        "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
        "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
        "wrist_flex": Motor(4, "sts3215", MotorNormMode.DEGREES),
        "wrist_roll": Motor(5, "sts3215", MotorNormMode.DEGREES),
        "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
    })
    bus.calibration = {n: MotorCalibration(**c) for n, c in cal.items()}
    bus.connect()
    return bus


def traj_home_point_point(home, point, label, hold_s=0.8, move_s=2.0, scale=1.0, hz=HZ):
    """HOME -> point -> hold -> HOME 的梯形插值轨迹, 返回 (N,6) 动作序列 + label idx。"""
    h = np.array([home[m] for m in MOTORS])
    p = h + (np.array([point[m] for m in MOTORS]) - h) * scale

    def seg(a, b, dur):
        n = int(dur * hz)
        t = np.linspace(0, 1, n)
        s = np.where(t < .5, 2*t*t, 1-2*(1-t)**2)      # 梯形(平滑起停)
        return a + (b - a) * s[:, None]

    tr = np.vstack([seg(h, p, move_s), np.tile(p, (int(hold_s*hz), 1)), seg(p, h, move_s),
                    np.tile(h, (int(0.3*hz), 1))])
    return tr, "ABC".index(label)


def run_episode(bus, tr, li):
    """真臂执行一条轨迹并记录。返回 obs(N,9), action(N,6)。"""
    onehot = np.zeros(3); onehot[li] = 1.0
    obs, act = [], []
    for target in tr:
        for j, m in enumerate(MOTORS):
            bus.write("Goal_Position", m, float(target[j]))
        pos = bus.sync_read("Present_Position")
        obs.append([pos[m] for m in MOTORS] + list(onehot))
        act.append(target.copy())
        time.sleep(1.0 / HZ)
    return np.array(obs, dtype=np.float32), np.array(act, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--collect", type=int, default=0)
    ap.add_argument("--out", default=os.path.expanduser("~/services/robotics/reach_dataset.npz"))
    args = ap.parse_args()
    bus = make_bus()

    if args.demo:
        tr, li = traj_home_point_point(HOME, POINTS["A"], "A", scale=0.5, move_s=4.0)
        print("DEMO: 半幅慢速 A 轨迹, ~13 秒, 观察方向与幅度")
        obs, act = run_episode(bus, tr, li)
        print(f"完成 {len(obs)} 帧 | 起始 obs {obs[0,:6].round(1)} | 终点附近动作 {act[-40,:6].round(1)}")
        bus.disconnect(); return

    eps = []
    labels = "ABC" * ((args.collect // 3) + 1)
    labels = (labels * args.collect)[:args.collect]
    for i, lb in enumerate(labels):
        tr, li = traj_home_point_point(HOME, POINTS[lb], lb)
        obs, act = run_episode(bus, tr, li)
        eps.append({"obs": obs, "action": act, "label": lb})
        np.savez_compressed(args.out,                     # 增量保存: 挂了只丢当条
                            obs=np.stack([e["obs"] for e in eps]),
                            action=np.stack([e["action"] for e in eps]),
                            labels=np.array([e["label"] for e in eps]))
        print(f"  ep{i+1}/{args.collect} [{lb}] {len(obs)} 帧", flush=True)
        time.sleep(1.0)
    print(f"已存 {args.out}: {len(eps)} episodes")
    bus.disconnect()


if __name__ == "__main__":
    main()
