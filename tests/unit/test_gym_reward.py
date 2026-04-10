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
        cfg = RewardConfig(step_cost=0.0, look_at_enemy_reward=0.005)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["rays"][4, 1] = 0.4

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.005, places=6)

    def test_no_enemy_visible_does_not_add_look_reward(self) -> None:
        cfg = RewardConfig(step_cost=0.0, look_at_enemy_reward=0.005)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_strafing_observation_adds_strafing_reward(self) -> None:
        cfg = RewardConfig(step_cost=0.0, look_at_enemy_reward=0.0, strafing_reward=0.004)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["rays"][2, 1] = 0.5
        observation["state"][10] = 1.0
        observation["state"][13] = 1.0
        runtime.player_shoot_hold_active = True

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.004, places=6)

    def test_strafing_without_engagement_does_not_add_strafing_reward(self) -> None:
        cfg = RewardConfig(step_cost=0.0, look_at_enemy_reward=0.0, strafing_reward=0.004)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["rays"][2, 1] = 0.5
        observation["state"][10] = 1.0
        observation["state"][13] = 1.0

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_not_strafing_does_not_add_strafing_reward(self) -> None:
        cfg = RewardConfig(step_cost=0.0, look_at_enemy_reward=0.0, strafing_reward=0.004)
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_idle_penalty_is_suppressed_while_shoot_hold_active(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            idle_ticks_threshold=2,
            idle_cost=1.0,
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

    def test_stationary_shooting_without_hits_gets_penalty_after_grace(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            stationary_shoot_no_hit_cost=0.25,
            stationary_shoot_no_hit_grace_ticks=2,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shoot_hold_active = True

        first = tracker.step(runtime, None)
        second = tracker.step(runtime, None)
        third = tracker.step(runtime, None)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, -0.25, places=6)
        self.assertAlmostEqual(third.value, -0.25, places=6)

    def test_stationary_shooting_penalty_resets_when_hit_occurs(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            hit_reward=0.5,
            look_at_enemy_reward=0.0,
            stationary_shoot_no_hit_cost=0.25,
            stationary_shoot_no_hit_grace_ticks=2,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shoot_hold_active = True

        first = tracker.step(runtime, None)
        runtime.player_hits_total = 1
        second = tracker.step(runtime, None)
        third = tracker.step(runtime, None)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, 0.5, places=6)
        self.assertAlmostEqual(third.value, 0.0, places=6)

    def test_stuck_cost_applies_when_trapped_in_small_area(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            stuck_ticks_threshold=2,
            stuck_radius_epsilon=2.0,
            stuck_cost=0.4,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        first = tracker.step(runtime, None)
        runtime.player_world_x = 1
        runtime.player_world_y = 0
        second = tracker.step(runtime, None)
        runtime.player_world_x = 0
        runtime.player_world_y = 1
        third = tracker.step(runtime, None)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, -0.4, places=6)
        self.assertAlmostEqual(third.value, -0.4, places=6)


if __name__ == "__main__":
    unittest.main()
