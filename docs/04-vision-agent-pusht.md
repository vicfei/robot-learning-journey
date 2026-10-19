# 04 · pusht 视觉 agent 闭环：VLM 大脑 + VLA 小脑的增益测量

在 gym_pusht 上搭了 VLM-in-the-loop 的在线评测闭环：大脑（DeepSeek-Vision）低频决策、小脑（VLA 策略）连续出动作，三路对照（无大脑/真值大脑/VLM 大脑）。这轮实验的主产出不是正增益数字，而是一条**归因链**——它把"分层架构的增益传导"这件事测明白了。

## 1a · 指令文本通道：三路全零与执行层瓶颈

执行层用自训 smolvla（pusht 专家数据，3000 步），大脑通过任务指令文本注入（smolvla 有语言接口）：

| 对照 | 成功率 | coverage |
|---|---|---|
| base（固定指令） | 0/10 | 0.000 |
| oracle（真值方向指令） | 0/10 | 0.002 |
| vlm（DeepSeek-Vision 每 25 步动态指令） | 0/10 | 0.000（120 次调用） |

oracle 拿信息量上限的指令也救不动 → **瓶颈不在指令层在执行层**。四步归因把"执行层为什么不行"钉死：

1. 自建评测管线无 bug——官方 `lerobot/diffusion_pusht` 在同一管线 cov 0.43（ep4 达 0.93）
2. smolvla ckpt 过官方 lerobot-eval 也是 0%
3. 3000→20000 步加练（loss 0.064→0.023）成功率纹丝不动
4. → **smolvla×pusht×lerobot 0.4.4 组合训不出来**（与社区 issue #2354 对 0.4.x smolvla 仿真复现低分的怀疑同向）

插桩还拍到了行为克隆复合误差的现场：开局 coverage 0.634 的好局，策略一步把块推离目标，之后 300 步追随自身位置游走不恢复——回放协议 11° 的方向中位误差，闭环放大成 0% 成功率。

## 1b · waypoint 通道：执行层修复后增益通道打开

小脑换官方 diffusion_pusht，大脑的干预从"指令文本"改为"开局 waypoint"（agent 先绕到块的推动侧，再交给小脑推）——这本来就是 harness 派（ORA 等）的真实形态：

| 对照 | 成功率 | coverage |
|---|---|---|
| base（DP 全自主） | 0/10 | 0.320 |
| wpt-oracle（真值绕位） | **1/10** | **0.366**（成功局 152 步直推） |
| wpt-vlm（VLM 看图选位） | 0/10 | 0.345 |

分层增益通道打开：oracle 到上限时拿到首个成功例；VLM 落在 base 和 oracle 之间（cov +8%），说明其决策质量约为真值七成——但 10 eps 不足以对成功率下统计结论，40 eps 大样本是下一步。

## 方法论沉淀

- **执行层基线必须先验证**：分层增益测量里，小脑能力不足会把任何大脑增益吞掉（1a 的教训）
- **waypoint 通道 > 指令通道**：对无语言接口的小脑（DP 及任何策略），低频空间子目标是通用干预形式
- **oracle 是增益区间的标尺**：base→oracle 撑出 [地板, 上限]，真实大脑落在区间内的位置就是它的评分

## 踩坑记录

1. gym_pusht 观察图必须用 `env.unwrapped._render(visualize=False)`（96×96，与训练数据同源）；`render()` 是 680 可视化图，坐标系不同
2. DeepSeek 视觉模型名 `deepseek-v4-flash-vision-exp` 不在 /models 列表但可直调；深度推理型 13s/次，max_tokens 要给 8k 否则思考吃满没输出
3. VLM 输出 JSON 要做围栏剥离 + 首个 `{...}` 块提取，否则偶发解析回落
4. gym_pusht 安装：`uv pip install --python venv/bin/python gym_pusht`

复现脚本：`scripts/vla-distill/` 之外的 `exp_vision_agent.py` / `exp1b_waypoint.py`（机器侧留存），结果数据 `exp1_results.json` / `exp1b_results.json`。
