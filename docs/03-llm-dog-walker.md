# 03 · LLM 遛狗：robot-use agent 的第一个闭环

MIT Cheetah 仿真里搭了一个"一句话遛狗"闭环：LLM 读自然语言任务生成遥控指令序列，下发给四足机器人执行，用状态估计的位置反馈校验实际位移，误差超阈值时带着反馈重规划。推理/规划/执行/反馈恢复四要素第一次凑齐。

## 架构

```
"前进一米然后左转"
   │ LLM（DeepSeek，OpenAI 兼容 API，约束输出 JSON 指令序列）
   ▼
Executor ──pty──▶ mit_ctrl 键盘遥控线程（'2'行走 'w/s'平移 'q/e'转向 'x'清零）
   │                    Cheetah Convex MPC 执行
   ▼
Verifier ◀── LCM state_estimator（机身位置 + 四元数）
   │ 快照对比：body 系位移 / yaw 转角 vs 期望
   ▼
误差 > 0.25m / 20° → 带反馈重规划一次 → 再校验 → ✅/❌
```

实测（DeepSeek 规划）：

| 任务 | 位移实测 | 转角实测 | 误差 | 判定 |
|---|---|---|---|---|
| 前进一米然后左转 | 0.99m（期望 1.0） | +73°（期望 90°） | 0.01m / 17° | ✅ 一次达标 |
| 先前进半米，然后右转，最后后退一米 | 三段复合 | -73°（期望 -90°） | 0.07m / 17° | ✅ 一次达标 |

## 关键工程决策：指令怎么注入

`rc_control`（遥控设定结构体）是 mit_ctrl **进程内**的 C++ 全局变量，原生输入是 SBUS 串口（真机遥控器），仿真里没有这条通道——"独立 driver 进程直接写"不成立，除非先给 mit_ctrl 加 IPC（改动量不小于改本体）。

选定方案是 **pty 遥控，零 C++ 改动**：`pty.openpty()` 的 slave 端作为 mit_ctrl 的 stdin，`isatty` 检查为真，仓库里现成的键盘遥控线程（`CHEETAH_NO_RC=1` 激活）照常启动；Python 侧按时间表往 master 写按键字节。整套注入复用了已验证的键盘路径，一行 C++ 都没改。

另有一个配套补丁：sim 面板要人工点 Start，给 `SimControlPanel.cpp` 构造函数加了 `CHEETAH_AUTOSTART=1` 环境变量触发（自动选 MiniCheetah+Simulator，1.5 秒后自动点 Start），从此演示全程无人值守。

## 踩坑记录（按发现顺序）

1. **守护期时序**：mit_ctrl 起来后前 12 秒键盘线程强制 RECOVERY_STAND（覆盖初始化窗口），这期间发键会提前解除守护、指令不被消费。必须等满。
2. **turn 返回值双重角度转换**：wrap 后的度数又套了一层 `math.degrees`，-85° 被放大成 -4880° 的"疯转"读数，一度误导排查方向。教训：单位换算只在一处做。
3. **不同 sim 实例 'q' 键的 yaw 方向不一致**（根因未深究，疑与估计器/初始条件有关）。解法是运行时自标定：起步先微转 1.2 秒读 yaw 符号，方向键映射随之确定，对所有实例鲁棒。
4. **动态衔接要 settle**：前进停止瞬间立即转弯会让狗失稳打滚（yaw 的大旋转是真实的物理翻滚，不是测量错误）。停稳 2.5 秒再转；速度用单键 0.25m/s（0.5 会摔）。
5. **四元数双覆盖**：state_estimator 的姿态输出会整体符号翻转，带 roll/pitch 分量时会让 yaw 读数镜像。加了符号连续化（与上帧点积为负则取反）。
6. **量程标定**：固定按键时长 vs 实际位移有系统性偏差（加减速 + MPC 跟踪滞后），用系数标定（前进 ×0.9、转弯 ×0.9，90° 指令实测约 73°），残差交给闭环反馈吸收。
7. **pkill 自杀坑**：shell 命令行里 `pkill -f mit_ctrl` 会匹配到命令行自身的字符串把 shell 杀掉，表现为"静默无输出"。用 `pkill -f "mit_[c]trl"` 正则绕过。

## 复现要点

- 一键演示：`./walk_demo.sh "前进一米然后左转" llm`（mock/llm 可选，llm 需 `DEEPSEEK_API_KEY`/`ZHIPUAI_API_KEY`/`DASHSCOPE_API_KEY` 任一环境变量）
- 脚本在 `scripts/llm-dog-walker/`（driver 主体 + 一键演示 + 四元数诊断脚本）
- 前置：Cheetah 编译产物 + `CHEETAH_AUTOSTART` 补丁（sim）+ `CHEETAH_NO_RC` 键盘线程（mit_ctrl，仓库原有）
- LLM 侧零新依赖：urllib 手写 OpenAI 兼容调用，temperature 0.2，重规划轮把执行误差 JSON 喂回上下文
