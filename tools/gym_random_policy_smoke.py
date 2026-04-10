from __future__ import annotations

import argparse
from pathlib import Path
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.gym_env import UltimateTKEnv, gym_available


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run random-policy smoke test for UltimateTKEnv")
    parser.add_argument("--episodes", type=int, default=1, help="Episode count")
    parser.add_argument("--max-steps", type=int, default=500, help="Maximum steps per episode")
    parser.add_argument("--seed", type=int, default=123, help="Base random seed")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not gym_available():
        print("gymnasium dependency is missing. Install with: python3 -m pip install -e '.[ai]'")
        return 2

    env = UltimateTKEnv(
        project_root=str(PROJECT_ROOT),
        max_episode_steps=args.max_steps,
    )

    try:
        for episode in range(max(1, args.episodes)):
            obs, info = env.reset(seed=args.seed + episode)
            del obs
            terminated = False
            truncated = False
            step_count = 0
            reward_total = 0.0

            while not terminated and not truncated and step_count < args.max_steps:
                action = env.action_space.sample()
                obs, reward, terminated, truncated, info = env.step(action)
                del obs
                reward_total += reward
                step_count += 1

            print(
                "episode=%d steps=%d terminated=%s truncated=%s reason=%s game_completed=%s reward_total=%.3f"
                % (
                    episode,
                    step_count,
                    terminated,
                    truncated,
                    info.get("terminal_reason", ""),
                    info.get("game_completed", False),
                    reward_total,
                ),
            )
    finally:
        env.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
