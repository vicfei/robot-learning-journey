# 前沿笔记：Robot-Use Agent（2026 Q4）

> 方向笔记，记录行业正在发生什么、我判断它为什么重要、以及它和本仓库实验的关系。定期更新。
> 主要参考源：[Awesome-Robot-Use-Agent](https://github.com/kairunwen/Awesome-Robot-Use-Agent)（2026-09 创建，一个月 153 star，日更）及其[配套网站](https://kairunwen.github.io/Awesome-Robot-Use-Agent/)。

## 一句话定义

Robot-use agent：AI 系统把机器人当工具来用——推理用户目标、规划动作、通过感知与控制接口驱动机器人执行，并根据执行反馈评估进度、调整计划、从失败中恢复。

架构上是"大脑 + 小脑"分层：

```
Agent 层（大脑）：LLM/VLM 负责任务分解、代码/技能生成、失败检测、重规划
   │  skill API / 控制接口
执行层（小脑）：VLA 策略或经典控制器负责动作执行
```

## 为什么现在值得关注

三个信号叠加：

1. **大厂集体入场**。Anthropic 发了 Claude plays robotics（对比直接电机控制 / 生成控制器 / 预训练策略监督 / RL 训练四种接口范式）；DeepMind 的 Gemini Robotics ER 2 明确采用"高层决策 + VLA 执行"分工；GPT-6 Astra 被送上 RoboDojo 操控评测打榜。
2. **论文谱系成型**。地基（SayCan、Code as Policies、VoxPoser、ReKep、Inner Monologue，2022-2024）到前沿（Hi Robot 分层 VLA、ENPIRE/ASPIRE 真机自改进、Code-as-Monitor 失败检测）已经连成一条完整的技术演进线。
3. **社区整理速度**。上面那个 awesome list 一个月收录 221 篇资源 + 61 个 demo，说明产出密度。

学界的态度可以参考 Ken Goldberg 2026-09 的评论：编码智能体可以通过离线写/测/改机器人程序，弥合模型工程与机器人学习两条路线——real-to-sim-to-real 成为主流工作流之一。

## 论文阅读清单（按依赖顺序）

**地基（LLM 编排机器人的经典，2022-2024）**

| 论文 | 贡献 |
|---|---|
| SayCan (2022) | 语言模型提议 + 价值函数可行性打分，第一个像样的 LLM 机器人接口 |
| Code as Policies (2022) | LLM 直接生成可执行控制代码，而不是文本计划 |
| Inner Monologue (2022) | 把执行反馈（人话/感知结果）注入 LLM 上下文做闭环 |
| VoxPoser (2023) | LLM 输出 3D 值地图代替低层动作序列 |
| ReKep (2024) | 关键点约束作为 LLM 与低层控制之间的接口 |

**前沿（2025-2026，按主题）**

| 主题 | 代表工作 |
|---|---|
| 分层编排 | Hi Robot（开放指令的分层 VLA）；What Matters in Orchestrating Robot Policies（系统性研究） |
| 自改进循环 | ENPIRE / ASPIRE（真机上 agent 自己发现技能、改进策略）；RoboTTT（上下文扩展） |
| 失败检测与恢复 | AHA（失败推理 VLM）；Code-as-Monitor（约束感知的主动监控）；REFLECT |
| 评测 | RoboDojo（GPT-6 Astra 的榜）；EmbodiedBench；RoboCerebra（长程任务） |

## 与本仓库实验的映射

这个范式的每一层，本仓库已有对应物或计划：

| RUA 范式层 | 本仓库对应 | 状态 |
|---|---|---|
| 执行层：VLA | OpenVLA-7B 4-bit 推理 + smolvla 微调 | 已跑通 |
| 执行层：控制 | MIT Cheetah MPC、Go1 MJX RL | 已跑通 |
| 控制接口 | LCM→ROS 2 桥 + 键盘遥控协议 | 已跑通 |
| Agent 编排层 | **待做**：LLM 读自然语言任务 → 生成遥控序列 → 下发执行 → 状态反馈校验/重试 | 计划中 |

有意思的观察：autoresearch 那种"program.md 驱动 agent 自主做实验 + keep/discard 循环"的模式，和 ENPIRE 这类自改进 agent 的结构是同构的。缺的只是把闭环的一端从"LLM 训练任务"换成"机器人任务"。

## 下一步实验（规划）

最小可行版本一天可完成，复用现有资产接近 100%：LLM（API）读任务描述（如"前进一米然后左转"）→ 输出遥控指令序列 → 经 ROS 2 通道下发 Cheetah → 用 state_estimator 的位置反馈校验执行结果，失败则重规划。这一步走通，推理/规划/执行/反馈恢复四要素就都在自己机器上落地了。

## 跟踪方式

- RUA 仓库 star + 每月扫一次 Social Demos 区感受风向
- 用配套网站按主题检索，比翻 README 高效
- 新论文先读摘要和图，判断与本仓库哪层相关再决定是否精读
