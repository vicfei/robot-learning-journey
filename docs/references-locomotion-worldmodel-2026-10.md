# 参考 · 腿足 RL 技术栈与世界模型突破（2026-10 快照）

> 2026-10-27/29 两轮调研（microduck 七仓 + SuperMimic）。承接 references-robot-harness-landscape
> 的生态观察——那份管 harness 派，这份管训练派的省算力路线。

## 一 · microduck 生态：低成本腿足的完整开源链

一条自上而下的技术链，三个月 12.7k⭐ 的现象级产品（Pollen Robotics 双足鸭，25cm/800g）：

| 仓库 | 角色 | 要点 |
|---|---|---|
| pollen-robotics/microduck 12.7k⭐ | 产品本体（"鸭的大脑"） | Rust daemon、RK3566 上 50Hz 控制环驱动 15 舵机、跑 ONNX 策略、免变砖 OTA |
| microduck_rl 2.7k⭐ | 官方训练仓 | **mjlab(MuJoCo Warp) + PPO**，4096 envs 1-2h 出步态；sim2real 配方全公开（BAM 执行器物理 + 域随机化 + 齿隙仿真 + AGENTS.md 攻略手册） |
| mujocolab/mjlab 3.3k⭐ | 框架底座 | **Isaac Lab API × MuJoCo Warp**——免费开源不锁 NVIDIA 栈 |
| Rhoban/bam 577⭐ | sim2real 关键件 | 低成本舵机的扩展摩擦模型（空程/齿隙）辨识与仿真 |
| leggedrobotics/rsl_rl 3.1k⭐ | PPO 实现层 | ETH 经典（2021 至今） |
| jonathanhawkins/microduck-lab 151⭐ | 低算力奇迹 | **无 CUDA 的 Mac 训练** RL + 浏览器 viewer + 多机器人房间任务 |

**对本仓库的映射**：
1. 工作流 B（Cheetah 四足 RL）选型题的答案：**mjlab 取代 brax 考古**（warp 系胜出，生态已投票）
2. 8GB 消费卡从"被排除"变"可行"（microduck-lab 证明纯 CPU 可训；降 envs 即可）
3. **BAM 直接适配 SO-101 的 HX-30HM**（同类低成本总线舵机）——将来仿真预演的即插物理件
4. so_arm_agent 的架构参照：训练组件放姊妹仓（harness 仓保持纯净）、AGENTS.md 攻略手册模式、
   浏览器 viewer 演示哲学

## 二 · SuperMimic：世界模型路线的算力塌方（2026-10-26 发布，arXiv 2610.28480）

人形全身控制 + **可微世界模型**，真机 Unitree G1 完成侧翻/空翻。核心："一个循环、两个学习者"
——标准接触仿真器只收集数据，拟合**学出来的可微世界模型**，策略经 BPTT 解析梯度直接穿过
世界模型优化，**梯度永不穿过仿真器**（把 RL 试错换成可微优化）。

| | SuperMimic | SONIC（SOTA 基线） |
|---|---|---|
| 训练 | 1×H100 · 3 小时 | 128×L40 · 7 天 |
| GPU 时 | 3 | 21,000（**>1000× 缩减**） |
| 失败动作 | 0 | 179/129,514 |

口号即论点："Compute is no longer the bottleneck." 浏览器 Web demo 跑策略；
DiaoOrg/awesome-supermimic 一天 220⭐，复现潮正在启动。

## 三 · 省算力三条路线地图（frontier 框架升级）

训练派 vs harness 派的二元框架升级为三角：

| 路线 | 代表 | 机理 | 成熟度 |
|---|---|---|---|
| **世界模型梯度** | SuperMimic | 可微世界模型内解析优化策略 | 刚突破, 复现潮初期 |
| **RL 快速收敛** | squint（视觉 SAC, 分钟级） | 并行环境 + 经验复用 + 预处理 | 论文级验证 |
| **harness 免训练** | ORA / RoboHarness / 本仓库 03·06 号 | API 模型 + 确定性原语 + 代码否决 | 当下可用 |

对本仓库路线的含义：**RUA 押注依然正确（当下就能干活），但"训练线永久冻结"改写为
"搁置到世界模型路线下沉"**——>1000× 算力缩减意味着消费级复现只是时间问题；
SuperMimic 的 mimic 设定天然贴合示教数据，将来 SO-101 学抓取策略时的 36 条 reach
数据可能直接复用。跟踪锚点：awesome-supermimic 的 implementations 区 + mjlab 生态合流
（SuperMimic 用 MuJoCo 系物理, 与 mjlab 栈兼容——收敛公式：**MuJoCo 系物理 + 可微世界模型 + 小算力**）。
