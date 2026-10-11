# 02 · VLA 行为蒸馏：OpenVLA-7B 的知识能不能白嫖给 smolvla-450M

pusht 数据集上做了一次完整的行为蒸馏：7B teacher（OpenVLA，4-bit 量化推理）给 450M student（smolvla）打标，student 在 teacher 标注上训练，与专家数据基线、teacher 本尊做三路同卷对照。核心悬念是跨域——teacher 是 Bridge 数据（第三视角桌面操作）训的，没见过 pusht（俯视 96×96 二维推块）。

## 方法

三步流水线，两进程文件交接（OpenVLA 和 lerobot 在两个 venv 里，依赖互不相容，干脆不装包，用 png/npz 传文件）：

1. **打标**：抽 34 个 episode 共 4244 帧图像，OpenVLA-7B（NF4 4-bit）逐帧推理 7-DoF delta 动作，0.6s/帧、4.7GB 显存。
2. **动作映射**（本实验的核心工程决策）：teacher 输出 delta、pusht 动作是绝对像素坐标，选了**累积式闭环轨迹**——每个 episode 用真值 state 锚定起点，之后 `a[t] = clip(a[t-1] + k·M·(Δx,Δy))` 逐帧累积。映射参数（轴排列 M、缩放 k）在 340 帧 probe 批上一次性标定后冻结，训练与评测同源。
3. **蒸馏训练**：蒸馏数据集的观测通道保持真值、只换 action 为 teacher 轨迹，与专家基线完全相同的优化预算（3000 steps × bs16）。

评测协议：三路在**同一张考卷**上比——回放原专家数据集 episode 0/1 共 279 帧，对专家真值动作算 L2 误差和方向角差。

## 结果

| 同卷对照 | L2 误差 mean | 方向角差 median | <15° 占比 |
|---|---|---|---|
| Teacher（OpenVLA+映射） | 243.5px | 18° | 36% |
| Student（专家数据） | 119.2px | 11° | 67% |
| Student（蒸馏） | 146.5px | **7°** | **78%** |

## 结论（诚实版）

预 registered 的风险实锤了一半。probe 阶段就发现 teacher 动作与专家增量的相关性全线弱（|r|≤0.18，306 个样本解释约 3% 方差）——OpenVLA 跨域输出基本是带微弱方向信号的随机游走，teacher 本尊考得最烂（L2 243px，接近半个画面）。

**但蒸馏 student 没有被传染**：L2 146.5 显著好于 teacher 的 243.5，方向一致性（7°/78%）反而超过了专家 student（11°/67%）。原因在架构：smolvla 是 state-conditioned 的，蒸馏数据的观测通道是真值（teacher 轨迹起点锚定、与真值强相关），student 借此恢复了位置结构；同时 teacher 的弱方向信号经 450M student 拟合平滑后被保留甚至放大。

所以"白嫖"不是全输：**死穴在绝对坐标系对齐（L2 +23%），方向先验可以白嫖（-4°）**。这是一张结构化的失败地图，不是干净的胜负。

局限：数据量不对等（4244 vs 25650 帧）、方向角差指标对绝对漂移不敏感、单 seed、回放协议非在线成功率。

## 踩坑记录

1. **lerobot 0.4.4 自建数据集的三个坑**：`create` 的 root 参数要直接传数据集目录；features 的 shape 必须用 tuple 声明（校验代码拿 `np.shape`（tuple）和声明的 list 直接比较，永不相等，报错误导性强）；`add_frame` 只认 numpy/PIL，torch tensor 会掉进报错分支。
2. **训练拉 HF 底座模型**要 `HF_HUB_OFFLINE=1`（直连必挂；即使本地有缓存，HEAD 请求重试五次每次八秒）。
3. **pusht 图像 tensor 是 float32 CHW [0,1]**，喂给吃 PIL 的模型前要 ×255 转 uint8。
4. 映射 probe 要对齐增量对：teacher 第 t 帧 delta 对应真值 gt[t+1]-gt[t]，错位一对全乱。

## 复现要点

- 打标管线三脚本 + teacher 评测在 `scripts/vla-distill/`（extract → label → build，映射参数冻结在 map_config.json，训练/评测共用）
- 训练配置对齐专家基线只改 dataset root 和 output_dir
- 硬件水位：打标 4.7GB（NF4 7B），蒸馏训练 3.4GB，两者与评测可在 8GB 卡上错峰
