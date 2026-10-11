# 学习路线图

> 12-18 个月的计划，从"跑通了实验"到"讲得透原理、有真机作品"。边走边修订，每次修订记录日期。

## 知识树（按依赖顺序）

```
第一层  机器学习地基        神经网络/损失/梯度下降/过拟合
第二层  深度学习工程        张量与显存/量化/训练 vs 推理
第三层  ┌ 路线 A：模型控制   运动学/动力学/MPC/WBC
        └ 路线 B：学习驱动   模仿学习/强化学习
第四层  系统与集成          ROS 2/仿真器/sim-to-real
第五层  前沿专题            VLA/蒸馏/robot-use agent
```

原则：不需要学完再回头——每个概念都有已跑过的实验对应，最佳路径是回头看实验发现不懂、精准补那一块。

## 各层资源与目标

| 层 | 资源 | 够用标准 |
|---|---|---|
| 一 | 李宏毅 ML 课（B 站）/ 李沐《动手学深度学习》(d2l.ai) | 能解释 PushPuck 实验里 DP 欠拟合现象 |
| 二 | d2l 后半 + HuggingFace 官方课程 | 能算出 7B 模型 4-bit 为何是 4.4GB |
| 三A | Tedrake《Underactuated Robotics》（免费在线，MIT Cheetah 出自该实验室） | 能推导桥里足端 FK；讲清 Convex MPC 滚动时域 |
| 三B | Berkeley CS285（Levine，YouTube 免费）；RL 入门配 Sutton & Barto 前六章 | 能讲 PPO clip 项设计；ACT CVAE 如何处理多模态 |
| 四 | ROS 2 官方 tutorials + fishros.com（中文） | 能解释 DDS 发现机制和 TF 树 |
| 五 | Stanford CS336；RUA 论文清单（见 frontier 笔记） | 复现其中一篇的关键消融 |

如果只深学两样：CS285 + Underactuated Robotics——正好覆盖"模型驱动 vs 学习驱动"两条路线的理论两侧。

## 时间线

| 阶段 | 内容 | 产出 |
|---|---|---|
| 第 1-3 月 | 补一、二层；SO-101 真机闭环；现有实验整理成文档 | 真机 teleop 采集→训练→部署记录 |
| 第 3-9 月 | 深入一条主线（VLA 或 RL 二选一）；复现 2-3 篇论文；技术博客 | 复现报告 + 博客 |
| 第 9-18 月 | 开源项目贡献 PR（LeRobot/MJX 生态）；一个有数字的完整项目 | 可展示的项目 |

## 修订记录

- 2026-10-11 初版。基于已完成的四条实验线（模仿学习/四足 MPC+RL/VLA/ROS 2 桥）倒推知识缺口；前沿方向锁定 robot-use agent（见 frontier-2026q4.md）。
