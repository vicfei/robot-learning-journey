# 参考 · LLM agent 机器人 harness 生态快照

> 2026-10-16 调研快照（star 数为当日值，会过时）。起因：02/03 两个实验的产出考虑独立建仓，
> 需要摸清同类仓库的生态位与差异化空间。

## 总览

| 仓库 | 一句话定位 | stars | 创建 | 阶段 | 语言 |
|---|---|---|---|---|---|
| [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) | π 系 VLA 官方开源：π0/π0-FAST/π0.5 模型 + 微调框架 | 14.2k | 2024-10 | 成熟，持续更新 | Python |
| [BinceQu/RoboHarness](https://github.com/BinceQu/RoboHarness) | "不训练的 harness 打败 VLA"：视觉点击+光流跟踪+几何约束给 LLM 当控制面板 | 245 | 2026-10 | 一周新仓 | Python |
| [nssmd/RoboRSI](https://github.com/nssmd/RoboRSI) | 多 agent 自进化框架（Manager/Planner/Engineer/Reviewer + 技能树固化） | 142 | 2026-08 | 有论文+真机 demo | Python |
| [xiao-yang25/robot-harness](https://github.com/xiao-yang25/robot-harness) | 机器人执行运行时：动作可观测/可中断/可组合的 C++17 core + ROS 2/Nav2 | 84 | 2026-09 | 早期，CI 全绿 | C++ |
| [dingkaihu63/dsh-robotic-harness](https://github.com/dingkaihu63/dsh-robotic-harness) | DeepSeek Harness 生态的机器人插件套件（URDF 检查/MuJoCo/故障注入/诊断） | 24 | 2026-08 | Demo 期 | Python |

**生态位判断**：四个 harness 全是 2026 年 8-10 月的新仓库——"LLM agent 的机器人执行层"
是正在爆发的品类；同时 RoboHarness 以标题公开宣战 VLA 训练派（"A Simple Harness
Outperforms VLA and World Action Models"），训练派 vs harness 派的路线之争正在上演。

## 逐库要点

### openpi（训练派正统）

π0/π0-FAST/π0.5 三个 VLA 模型 + 10k+ 小时机器人数据预训练的 base checkpoint，支持 LoRA
微调到自有数据集（`fsdp_devices` 可配单卡）。对本仓库蒸馏方向的意义：**π0.5（3B
PaliGemma 底座）是比 OpenVLA-7B 更新更强的 teacher 候选**，且 3B 量级在 8GB 消费卡上
做 4-bit 推理比 7B 从容得多。

### RoboHarness（训练派反方旗帜）

完全不训练模型：LLM 在 2D 图上点关键点 → 光流跟踪 + 深度反投影持续回报位置 → LLM 组合
几何约束原语动作 → 闭环验证。BEHAVIOR Challenge 2025 参赛，Claude Code + Qwen3.8 +
R1 Pro 真机，验证机 48GB。02 号实验里"teacher 跨域动作与专家相关性 |r|≤0.18"的发现，
恰好是这场争论中训练派困境的量化证据。

### RoboRSI（学术重型）

四角色 agent 分工（Manager/Planner/Engineer/Reviewer）+ 任务-技能树 + Top-down Skill
Refinement：在线探索的解固化为代码、执行数据反哺学习策略、失败回溯到最早责任节点。
LIBERO 56% vs 最强 baseline OpenETA 50.7%。**benchmark 呈现范式最值得抄**：
success/coverage 双指标 + baseline 对照表。

### robot-harness（执行层基础设施）

最"基础设施"取向：C++17 core 做执行仲裁（三问："May this action run? May this result
be used? Is the previous work settled?"），接 Nav2/Gazebo，CI 徽章全绿。做的是移动底盘
执行层，与 LLM 侧 harness 互补而非竞争。

### dsh-robotic-harness（插件化路线样本）

DeepSeek Harness 生态的机器人插件套件，100+ 工具/25 技能清单化包装，仅 Windows 本地
验证。展示了一条发布路线：**作为某 agent 生态的插件套件发布**，而非独立框架。

## 对自家三个建仓方向的影响

1. **cheetah-ros2-bridge：空白依旧，且更被需要**。五库碰的平台是
   BEHAVIOR/LIBERO/Nav2/R1 Pro，无一做 MIT Cheetah/LCM；robot-harness 反而证明
   "机器人栈接入 agent 生态"有真实需求——桥正是 Cheetah 接入这类栈的底座。
2. **cheetah-llm-driver：赛道热但平台错位，差异化成立但要补强**。Cheetah 四足无人做，
   pty 零改动注入是最小依赖实现（对比 RoboHarness 的 48GB 验证机 + BEHAVIOR 场景数据）。
   待补：任务集成功率表（RoboRSI 范式）、双语 README。
3. **vla-distill-pipeline：路线之争是背景板，负面结果是弹药**。差异化主张保持
   "任意本地 LeRobot 数据集 + 4-bit teacher + 消费级显卡"，π0.5 列为下一 teacher 候选。

## 可直接借鉴的招

| 来源 | 招 | 用在哪 |
|---|---|---|
| RoboRSI | success/coverage + baseline 对照表 | 遛狗任务集评测、蒸馏报告 |
| RoboHarness | reference_results/ 复现契约 + 双语 README | 两个候选仓库的包装 |
| robot-harness | CI 徽章（e2e 测试挂 GitHub Actions） | cheetah-ros2-bridge |
| dsh | 插件化发布路线 | 不独立建仓时的备选 |
