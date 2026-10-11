# robot-learning-journey

Learning embodied AI from scratch, on a single gaming laptop (RTX 4060 8GB) running Ubuntu in WSL2. No cluster, no workstation - if it can run there, it can run anywhere.

The goal: understand how modern robot learning actually works by running every piece of it end to end, and writing down what broke along the way.

## What is in here

| Track | Topic | Status |
|---|---|---|
| 01 | Imitation learning: hand-coded expert -> LeRobotDataset -> ACT / Diffusion Policy on a custom MuJoCo task | done |
| 02 | Quadrupeds, both ways: MIT Cheetah MPC (model-based) and Unitree Go1 with MJX PPO (learning-based) | done |
| 03 | VLA models: OpenVLA-7B 4-bit inference vs smolvla-450M fine-tuning | done |
| 04 | LCM -> ROS 2 bridge to watch a 2019-era MPC stack in rviz | done |

Each doc in `docs/` follows the same shape: what I tried, the numbers I got, and the list of things that broke before it worked. The failure notes are the point - they were the expensive part.

Beyond the experiment logs, two living docs track the direction of travel: [frontier notes](docs/frontier-2026q4.md) (what the field is converging on, with a reading list) and the [roadmap](docs/roadmap.md) (knowledge gaps, resources, timeline).

## Why this exists

Most "getting started" material stops at `pip install` and a happy-path demo. The gap between that and actually running experiments on constrained hardware is where I spent most of my time, so this repo records the whole gap: version archaeology, driver quirks, memory limits, and the workarounds.

## Environment

Single laptop: RTX 4060 8GB, 20-core CPU, 19GB RAM for the Linux side. Everything runs user-space (no sudo, no system packages), which forced some unusual solutions documented along the way. See `docs/00-environment.md`.
