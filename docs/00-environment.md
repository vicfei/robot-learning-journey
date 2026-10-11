# 00 · 硬件与软件环境

一台游戏笔记本上跑完全部实验，没有服务器。记录环境是为了说明后面所有数字的上下文——8GB 显存决定了每一步的做法。

## 硬件

- GPU: RTX 4060 Laptop, 8GB 显存
- CPU: 14 核 20 线程
- 内存: 19GB（Linux 侧可见）
- 系统: Windows 11 + WSL2 (Ubuntu 24.04)，图形走 WSLg

## 关键约束（它们塑造了所有方案）

1. **无 sudo、无系统包管理**。apt 源走的代理已失效且无 root 权限，一切依赖走用户级方案：
   - Python 一律 uv venv，互不污染
   - C++ 工具链（Qt5/Eigen/LCM，编译 MIT Cheetah 用）从 deb 包解压到用户目录 + 一个环境脚本
2. **huggingface.co 直连不通**，数据集和权重走镜像；GitHub 大文件断流时有发生，备了一条 SSH 跳板的通道。
3. **显存 8GB 是硬顶**。7B 模型推理必须 4-bit（NF4），训练只能跑 450M 级别学生模型。GPU 并行仿真（MJX）反而宽裕：物理仿真显存占用远小于神经网络。

## 实测资源水位（供同配置参考）

| 工作负载 | 显存 | 备注 |
|---|---|---|
| Diffusion Policy 训练（PushPuck） | ~5.1GB | GPU 利用率 98% |
| MJX PPO（1024 并行环境 Go1） | ~4GB | 吞吐 12.9 万步/秒 |
| OpenVLA-7B 4-bit 推理 | 4.4GB | 0.6s/步 |
| smolvla 训练 | ~3.4GB | batch 16 |
