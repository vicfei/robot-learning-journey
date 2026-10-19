# 05 · SO-ARM101 真机点亮与首批数据：从开箱到 36 条示教轨迹

SO-101 到货当天走完：开箱接线 → 通信架构攻坚 → 点亮 → 校准 → 度数级控制 → 程序专家 36 条轨迹 + 四维质量验证。中间跨过了 WSL2 无 sudo、内核驱动缺失、usbipd 失败、非标舵机批次四层障碍——每层都有可复用的解法。

## 通信架构：TCP 桥（usbipd 死路之后）

WSL2 接 USB 舵机总线的标准路（usbipd-win）在本机持续 `Attach Request Failed`；且微软 WSL2 内核的 ch341 驱动不支持 CH343（PID 55d3）、无内核 headers 编不了 WCH 官方驱动。最终架构：

```
WSL lerobot/SDK ──socket://<winIP>:9999──▶ Windows 串口桥(python, 自动扫波特率)
                                              │ COM3 @ 1Mbps 8N1
                                              ▼
                                     BusLinker 模块 → 6× HX-30HM 舵机
```

pyserial 原生支持 `socket://` URL，lerobot 的 `--robot.port` 直接吃这个地址。

## 套装档案（国产豪华版）

- 舵机 HX-30HM（Feetech 协议兼容，型号号 777），**出厂 1Mbps 8N1**（不是常见文档的 115200——桥的波特率自动扫描发现的）
- ID1-6 = shoulder_pan / shoulder_lift / elbow_flex / wrist_flex / wrist_roll / gripper，卖家预装预设
- 双相机：30W（640×480，广角定焦，光学模糊属正常档）+ 200W（备用升级）

## 通信可靠性的四层 patch（全在两侧脚本/SDK 内，零系统改动）

| 层 | 问题 | 修法 |
|---|---|---|
| SDK 串口打开 | scservo_sdk 不认 socket:// | patch setupPort 走 serial_for_url |
| SDK 超时 | 1Mbps 名义超时窗几百 μs，TCP RTT 1-2ms | tx_time_per_byte 垫底 5ms/字节 |
| SDK 残留 | 迟到字节污染下一包（"ID1 好/ID2/3 脏包/ID4-6 静默"级联错位） | txPacket 前自动 flush RX |
| lerobot 重试 | 群读/写路径默认重试 0，桥上偶发解析失败即抛 | motors_bus 12 处 num_retry 0→3 |

桥本身 v3.2：读线程 20ms 超时可退出（断开后句柄干净释放——修"COM3 拒绝访问"崩溃）、COM 打开重试、主循环异常全兜、断连日志降噪。

## 校准与控制闭环

lerobot-calibrate 全流程通过（中间位 + 除 wrist_roll 外逐关节极限记录）。双向验证：手工摆中位读数 ≈0°；指令 20° 实到 18.6°、爪子 80%→78.6%——度数级控制闭环。

## 首批数据：程序专家 + 36 条 reach 轨迹

任务：HOME ↔ A/B/C 三点 reach（梯形插值专家，30Hz 写目标+同步读反馈）。数据四维验证全优：

| 维度 | 结果 |
|---|---|
| 完整性 | 36 条 × 153 帧，A/B/C 各 12 |
| 跟踪滞后 | 中位 1.43°（lift 3.6° 最大=重力抗阻，物理合理） |
| 运动范围 | 全部命中设计值 |
| 专家确定性 | 同标签到达段跨条目 std < 0.4°（教科书级可复现） |

这是 01 号 PushPuck"手写专家"方法论的真机版，也是后续 smolvla 真机微调的数据底座。

## 排障铁律（这轮最值钱的经验）

1. **先抓原始字节再信上层解析**——"直连严格测试 0/6"曾被当成硬件故障，实为测试脚本解析 off-by-one；舵机回复的原始字节一直是标准的
2. **强杀串口进程会卡死 COM 句柄**——重插 USB 是万能复位
3. **长任务采集必须增量落盘**——首批 36 条曾因 ep30 桥抖全灭（全采完才保存）
4. 管道 `| tail` 会缓冲全部输出直到进程退出——后台任务的"零输出"先查管道再怀疑进程

## 相机链路

Windows 侧 OpenCV 捕获 → MJPEG HTTP 流（多部分响应）→ WSL `cv2.VideoCapture(url)` 实测 30fps。lerobot record 的相机 url 配置留待带视觉采集时接。

## 复现工件

- `scripts/so101/serial_bridge.py` —— 串口桥 v3.2（波特率自动扫描 + 全部健壮性修复）
- `scripts/so101/camera_stream.py` —— 相机 MJPEG 流服务（--list 枚举 /shot 单帧）
- `scripts/so101/expert_reach.py` —— 程序专家采集器（--demo 安全试跑 / --collect 增量采集）
