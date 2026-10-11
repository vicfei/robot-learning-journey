"""LLM 遛狗 · 工作流 D 最小闭环（ros2 env 运行）。

架构: 自然语言任务 → Planner(LLM/mock) 生成指令序列 → Executor(pty 喂键遥控 mit_ctrl)
      → Verifier(LCM state_estimator 位置反馈) 校验实际位移/转角 → 误差超阈值带反馈重规划一次。

用法:
  micromamba run -n ros2 python llm_dog_walker.py --planner mock --task "前进一米然后左转"
  micromamba run -n ros2 python llm_dog_walker.py --planner llm --task "..."   # 需 ZHIPUAI_API_KEY 或 DASHSCOPE_API_KEY
前提: sim 已启动并已点 Start（run_cheetah_ros.sh 的前半流程）。

指令语义（复用 mit_ctrl 键盘线程, 零 C++ 改动）:
  键: 1=站立 2=行走(MPC) 0=急停 w/s/a/d=平移±0.25 q/e=转向±0.5 x=清零速度
"""
import os, sys, json, math, time, argparse, threading, subprocess, pty, select

BUILD = os.path.expanduser("~/services/cheetah-software/build/user/MIT_Controller/mit_ctrl")
LCM_STATE_URL = "udpm://239.255.76.67:7667?ttl=1"
LCM_CTRL_URL = "udpm://239.255.77.77:7667?ttl=1"

# ============================================================ Verifier: LCM 位置反馈
class PoseListener(threading.Thread):
    """订阅 state_estimator, 维护最近 p/yaw。"""

    def __init__(self):
        super().__init__(daemon=True)
        sys.path.insert(0, os.path.expanduser("~/services/cheetah-software/lcm-types/python_gen"))
        import lcm
        from state_estimator_lcmt import state_estimator_lcmt
        self.lc = lcm.LCM(LCM_STATE_URL)
        self.lc.subscribe("state_estimator", self._on)
        self.msg_type = state_estimator_lcmt
        self.pose = None  # (x, y, yaw)
        self.n = 0
        self._q_last = None
        self._lock = threading.Lock()

    def _on(self, ch, data):
        import numpy as np
        m = self.msg_type.decode(data)
        q = np.array(m.quat)
        # 四元数双覆盖连续化: q 与 -q 等价, 估计器输出会符号翻转;
        # 带 roll/pitch 时翻转会让 yaw 读数镜像 —— 与上帧点积为负则取反
        with self._lock:
            if self._q_last is not None and float(np.dot(q, self._q_last)) < 0:
                q = -q
            self._q_last = q.copy()
        w, x, y, z = q
        yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        with self._lock:
            self.pose = (m.p[0], m.p[1], yaw)
            self.n += 1

    def run(self):
        while True:
            self.lc.handle_timeout(200)

    def get(self):
        with self._lock:
            return self.pose

    def wait(self, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            p = self.get()
            if p is not None and self.n > 50:
                return p
            time.sleep(0.2)
        raise RuntimeError("state_estimator 无数据（sim 没起或没点 Start?）")


def wrap_deg(d):
    return (d + 180) % 360 - 180


# ============================================================ Executor: pty 键盘遥控
class DogExecutor:
    def __init__(self, verbose=True, boot_wait=13.0):
        self.verbose = verbose
        self._loco = False
        env = dict(os.environ)
        env.update(CHEETAH_NO_RC="1", LCM_DEFAULT_URL=LCM_CTRL_URL)
        self.master, slave = pty.openpty()
        self.proc = subprocess.Popen(
            [BUILD, "m", "s"], stdin=slave, stdout=slave, stderr=slave,
            cwd=os.path.dirname(BUILD), env=env, close_fds=True)
        os.close(slave)
        os.set_blocking(self.master, False)
        # 守护期 ~12s: RobotRunner 初始化 + 键盘线程强制 RECOVERY_STAND（狗站起来）
        # 此期间发键会提前解除守护, FSM 未就绪时指令不被消费 —— 必须等满
        time.sleep(boot_wait)
        self.drain()

    def drain(self):
        try:
            while True:
                s = os.read(self.master, 65536)
                if not s:
                    break
                if self.verbose:
                    sys.stdout.write(s.decode(errors="replace"))
                    sys.stdout.flush()
        except (BlockingIOError, OSError):
            pass

    def key(self, c, wait=0.15):
        os.write(self.master, c.encode())
        time.sleep(wait)
        self.drain()

    def enter_locomotion(self):
        if not self._loco:
            self.key("2", 2.0)   # 进 LOCOMOTION 并给 FSM 切换时间
            self._loco = True

    def forward(self, meters, listener, speed=0.25):
        """前进/后退 meters 米。时间系数 0.75 来自实测标定(1.0m@0.5m/s 实走 1.35m)。"""
        p0 = listener.get()
        k = "w" if meters >= 0 else "s"
        n_w = max(1, round(speed / 0.25))
        t = abs(meters) / speed * 0.9 + 0.4   # 0.25m/s 实测标定(0.72时欠走到0.82m)
        self.enter_locomotion()
        for _ in range(n_w):
            self.key(k)
        time.sleep(max(t, 0.5))
        self.key("x", 0.3)
        time.sleep(2.5)   # 停稳(立即转弯会失稳打滚, 实测教训)
        p1 = listener.get()
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        c, s = math.cos(p0[2]), math.sin(p0[2])
        return dx * c + dy * s, t   # body 前向分量

    def calibrate_turn_sign(self, listener):
        """实测发现不同 sim 实例 'q' 产生的 yaw 方向不一致（未深究根因）——
        运行时微转 1.2s 自动标定 'q' 的 yaw 符号。"""
        self.enter_locomotion()
        p0 = listener.get()
        self.key("q")
        time.sleep(1.2)
        self.key("x", 0.3)
        time.sleep(1.0)
        p1 = listener.get()
        d = wrap_deg(math.degrees(p1[2] - p0[2]))
        self._q_sign = 1.0 if d >= 0 else -1.0
        print(f"  [标定] 'q' 微转 1.2s -> yaw {d:+.0f}° (sign={self._q_sign:+.0f})")
        return self._q_sign

    def turn(self, degrees, listener, omega=0.5):
        """转向 ±degrees。方向键由运行时标定决定（见 calibrate_turn_sign）。"""
        p0 = listener.get()
        key = "q" if degrees * getattr(self, "_q_sign", 1.0) > 0 else "e"
        n = max(1, round(omega / 0.5))          # 按键次数 = 目标角速度/单键增量
        t = abs(degrees) / 180 * math.pi / omega * 0.9 + 0.3
        self.enter_locomotion()
        print(f"    [turn-debug] key={key}x{n} t={t:.1f}s p0_yaw={math.degrees(p0[2]):+.0f}°")
        for _ in range(n):
            self.key(key)
        curve = []
        t0 = time.time()
        while time.time() - t0 < max(t, 0.5):
            pp = listener.get()
            curve.append(round(math.degrees(pp[2])))
            time.sleep(0.3)
        self.key("x", 0.3)
        time.sleep(1.0)   # 停稳再取姿态
        p1 = listener.get()
        print(f"    [turn-debug] yaw曲线: {curve}")
        return wrap_deg(math.degrees(p1[2] - p0[2]))

    def stop(self):
        try:
            self.key("x", 0.2)
            self.key("1", 0.2)   # 回站立
        except OSError:
            pass

    def close(self):
        self.stop()
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


# ============================================================ Planner: LLM / mock
SYS_PROMPT = """你是四足机器人 Cheetah 的任务规划器。把自然语言任务翻译成遥控指令序列。
可用指令（JSON 数组, 顺序执行）:
  {"action": "forward", "meters": <float>}    前进(米)
  {"action": "back", "meters": <float>}       后退(米)
  {"action": "turn", "degrees": <float>}      转向(度, 正=左转, 负=右转)
只输出 JSON 数组, 不要任何其他文字。例: 前进一米然后左转 -> [{"action":"forward","meters":1.0},{"action":"turn","degrees":90}]"""


def plan_with_llm(task, feedback=None):
    """OpenAI 兼容 chat/completions。支持 DeepSeek/智谱(ZHIPUAI)/阿里(DASHSCOPE)。"""
    import urllib.request
    if os.environ.get("DEEPSEEK_API_KEY"):
        url = "https://api.deepseek.com/v1/chat/completions"
        key, model = os.environ["DEEPSEEK_API_KEY"], os.environ.get("LLM_MODEL", "deepseek-v4-flash")
    elif os.environ.get("ZHIPUAI_API_KEY"):
        url, key = "https://open.bigmodel.cn/api/paas/v4/chat/completions", os.environ["ZHIPUAI_API_KEY"]
        model = os.environ.get("LLM_MODEL", "glm-4.6")
    elif os.environ.get("DASHSCOPE_API_KEY"):
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        key, model = os.environ["DASHSCOPE_API_KEY"], os.environ.get("LLM_MODEL", "qwen-plus")
    else:
        raise SystemExit("需要 DEEPSEEK_API_KEY / ZHIPUAI_API_KEY / DASHSCOPE_API_KEY（或 --planner mock）")
    msgs = [{"role": "system", "content": SYS_PROMPT}]
    if feedback:
        msgs.append({"role": "user", "content": f"任务: {task}"})
        msgs.append({"role": "user", "content":
                     f"上一轮执行误差反馈, 请只输出修正增量指令: {feedback}"})
    else:
        msgs.append({"role": "user", "content": f"任务: {task}"})
    req = urllib.request.Request(url, data=json.dumps({
        "model": model, "messages": msgs, "temperature": 0.2,
    }).encode(), headers={"Authorization": f"Bearer {key}",
                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    text = out["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    return json.loads(text)


def plan_mock(task, feedback=None):
    """确定性解析: 中文任务词 → 指令序列。闭环联调用。"""
    import re
    if feedback:   # 修正增量: 直接按误差生成
        return [{"action": "forward", "meters": round(feedback.get("meters_err", 0), 2)},
                {"action": "turn", "degrees": round(feedback.get("degrees_err", 0), 1)}]
    cmds = []
    cn = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    def num(s, default):
        if not s:
            return default
        s = s.replace("两", "2").replace("一", "1")
        return float(cn.get(s, s))

    pat = re.compile(r"(前进|后退)([\d零一二两三四五六七八九十\.]+)?米?|(左|右)转([\d零一二两三四五六七八九十\.]+)?度?")
    for m in pat.finditer(task):
        if m.group(1):
            cmds.append({"action": "forward" if m.group(1) == "前进" else "back",
                         "meters": num(m.group(2), 1.0)})
        else:
            cmds.append({"action": "turn",
                         "degrees": num(m.group(4), 90.0) * (1 if m.group(3) == "左" else -1)})
    return cmds


# ============================================================ 闭环
TH_M, TH_DEG = 0.25, 20   # 位移/转角误差阈值


def execute_plan(cmds, ex, listener, tag):
    exp_m, exp_deg = 0.0, 0.0
    act_m, act_deg = 0.0, 0.0
    print(f"\n[{tag}] 执行 {len(cmds)} 条指令: {cmds}")
    for c in cmds:
        a = c["action"]
        if a in ("forward", "back"):
            sign = 1 if a == "forward" else -1
            got, _ = ex.forward(sign * abs(c.get("meters", 0.5)), listener)
            exp_m += sign * abs(c.get("meters", 0.5))
            act_m += got
            print(f"  {a} {c.get('meters')}m -> 实际 body 前向 {got:+.2f}m")
        elif a == "turn":
            got = ex.turn(c.get("degrees", 90), listener)
            exp_deg += c["degrees"]
            act_deg += got
            print(f"  turn {c.get('degrees')}° -> 实际 {got:+.0f}°")
        elif a == "stand":
            ex.key("1", 0.3)
        else:
            print(f"  未知指令 {c}, 跳过")
    return exp_m, act_m, exp_deg, act_deg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="前进一米然后左转")
    ap.add_argument("--planner", choices=["mock", "llm"], default="mock")
    ap.add_argument("--retries", type=int, default=1)
    args = ap.parse_args()
    plan = plan_mock if args.planner == "mock" else plan_with_llm

    print(f"== LLM 遛狗闭环 | planner={args.planner} | 任务: {args.task} ==")
    ex = DogExecutor(verbose=False)   # 先起 mit_ctrl（state_estimator 由它发布）
    listener = PoseListener()
    listener.start()
    p0 = listener.wait()
    print(f"位置反馈就绪: p=({p0[0]:.2f},{p0[1]:.2f}) yaw={math.degrees(p0[2]):.0f}°")
    ex.calibrate_turn_sign(listener)

    ok = False
    try:
        cmds = plan(args.task)
        for attempt in range(args.retries + 1):
            exp_m, act_m, exp_deg, act_deg = execute_plan(
                cmds, ex, listener, f"第{attempt+1}轮")
            m_err, d_err = exp_m - act_m, wrap_deg(exp_deg - act_deg)
            print(f"  累计期望 ({exp_m:+.2f}m, {exp_deg:+.0f}°) | "
                  f"实际 ({act_m:+.2f}m, {act_deg:+.0f}°) | "
                  f"误差 ({m_err:+.2f}m, {d_err:+.0f}°)")
            if abs(m_err) < TH_M and abs(d_err) < TH_DEG:
                ok = True
                print(f"\n✅ 任务达成（误差 < {TH_M}m/{TH_DEG}°）")
                break
            if attempt < args.retries:
                fb = {"meters_err": m_err, "degrees_err": d_err,
                      "actual": [round(act_m, 2), round(act_deg, 1)]}
                cmds = plan(args.task, feedback=fb)
                print(f"  误差超阈值, 重规划: {cmds}")
        if not ok:
            print("\n❌ 重试后仍未达标（如实记录）")
    finally:
        ex.close()
    pf = listener.get()
    print(f"终点: p=({pf[0]:.2f},{pf[1]:.2f}) yaw={math.degrees(pf[2]):.0f}° | "
          f"总位移 {math.hypot(pf[0]-p0[0], pf[1]-p0[1]):.2f}m")


if __name__ == "__main__":
    main()
