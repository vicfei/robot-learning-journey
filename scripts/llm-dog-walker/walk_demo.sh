#!/bin/bash
# LLM 遛狗 · 最小闭环演示（全自动，无需人工点面板）
# 用法: ./walk_demo.sh ["前进一米然后左转"] [mock|llm]
set -e
TASK="${1:-前进一米然后左转}"
PLANNER="${2:-mock}"
cd "$(dirname "$0")/../cheetah-software/build"
export MAMBA_ROOT_PREFIX=~/micromamba
export LCM_DEFAULT_URL='udpm://239.255.77.77:7667?ttl=1'

# 清残留
pkill -f "cheetah-software/build/sim/sim" 2>/dev/null || true
pkill -f mit_ctrl 2>/dev/null || true
sleep 1
rm -f /dev/shm/development-simulator 2>/dev/null || true

# 仿真器（AUTOSTART 补丁: 自动选 MiniCheetah+Simulator 并自动 Start）
nohup env CHEETAH_AUTOSTART=1 ~/bin/micromamba run -n cheetah ./sim/sim \
  > /tmp/cheetah_sim.log 2>&1 &
SIM_PID=$!
echo "等待 sim 自启动（面板自动点 Start）..."
for i in $(seq 1 60); do
  if ls /dev/shm/ 2>/dev/null | grep -q development-simulator && kill -0 $SIM_PID 2>/dev/null; then
    echo "sim OK (pid $SIM_PID)"; break
  fi
  if ! kill -0 $SIM_PID 2>/dev/null; then echo "sim DIED, log:"; tail -5 /tmp/cheetah_sim.log; exit 1; fi
  sleep 1
done

# 遛狗闭环（driver 内部自己 spawn mit_ctrl）
~/bin/micromamba run -n ros2 python ~/services/ros2-bridge/llm_dog_walker.py \
  --planner "$PLANNER" --task "$TASK"
STATUS=$?

kill $SIM_PID 2>/dev/null || true
exit $STATUS
