from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.reward import RewardConfig, RewardTracker
from ultimatetk.core.state import RuntimeState


class GymRewardTests(unittest.TestCase):
    def test_enemy_visible_observation_adds_look_reward(self) -> None:
        cfg = RewardConfig(step_penalty=0.0, look_at_enemy_reward=0.005)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((16,), dtype=np.float32),
        }
        observation["rays"][4, 1] = 0.4

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.005, places=6)

    def test_no_enemy_visible_does_not_add_look_reward(self) -> None:
        cfg = RewardConfig(step_penalty=0.0, look_at_enemy_reward=0.005)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((16,), dtype=np.float32),
        }

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_idle_penalty_is_suppressed_while_shoot_hold_active(self) -> None:
        cfg = RewardConfig(
            step_penalty=0.0,
            idle_ticks_threshold=2,
            idle_penalty=1.0,
            look_at_enemy_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shoot_hold_active = True

        first = tracker.step(runtime, None)
        second = tracker.step(runtime, None)
        third = tracker.step(runtime, None)

        self.assertEqual(first.stationary_ticks, 0)
        self.assertEqual(second.stationary_ticks, 0)
        self.assertEqual(third.stationary_ticks, 0)
        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, 0.0, places=6)
        self.assertAlmostEqual(third.value, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
