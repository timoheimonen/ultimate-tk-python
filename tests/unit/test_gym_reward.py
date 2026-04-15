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
        cfg = RewardConfig(
            step_cost=0.0,
            hit_reward=0.0,
            look_at_enemy_reward=0.005,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["rays"][4, 1] = 0.4
        runtime.player_hits_total = 1

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.005, places=6)

    def test_no_enemy_visible_does_not_add_look_reward(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.005,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_strafing_with_enemy_visible_adds_strafing_reward(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            hit_reward=0.0,
            look_at_enemy_reward=0.0,
            strafing_reward=0.004,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["rays"][2, 1] = 0.5
        observation["state"][10] = 1.0
        observation["state"][13] = 0.2
        runtime.player_hits_total = 1

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.004, places=6)

    def test_strafing_without_enemy_visible_no_reward(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            strafing_reward=0.004,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        observation["state"][10] = 1.0

        step = tracker.step(runtime, observation)
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_not_strafing_does_not_add_strafing_reward(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            strafing_reward=0.004,
            tile_discovery_reward=0.0,
        )
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
            tile_discovery_reward=0.0,
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
            tile_discovery_reward=0.0,
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
            tile_discovery_reward=0.0,
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
            tile_discovery_reward=0.0,
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

    def test_stuck_counter_resets_after_real_movement(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            stuck_ticks_threshold=2,
            stuck_radius_epsilon=2.0,
            stuck_cost=0.4,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        tracker.step(runtime, None)
        second = tracker.step(runtime, None)
        self.assertAlmostEqual(second.value, -0.4, places=6)

        runtime.player_world_x = 20
        moved = tracker.step(runtime, None)
        self.assertAlmostEqual(moved.value, 0.0, places=6)

        runtime.player_world_x = 20
        stationary_again = tracker.step(runtime, None)
        self.assertAlmostEqual(stationary_again.value, 0.0, places=6)

    def test_stuck_counter_resets_while_shooting_active(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            stuck_ticks_threshold=2,
            stuck_radius_epsilon=2.0,
            stuck_cost=0.4,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        tracker.step(runtime, None)
        second = tracker.step(runtime, None)
        self.assertAlmostEqual(second.value, -0.4, places=6)

        runtime.player_shoot_hold_active = True
        shooting = tracker.step(runtime, None)
        self.assertAlmostEqual(shooting.value, 0.0, places=6)

        runtime.player_shoot_hold_active = False
        after_release = tracker.step(runtime, None)
        self.assertAlmostEqual(after_release.value, 0.0, places=6)

    def test_level_complete_reward_scales_by_enemy_count(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            level_complete_reward_base=8.0,
            level_complete_reward_per_enemy=0.8,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        runtime.progression_event = "level_complete"
        runtime.enemies_total = 4
        step = tracker.step(runtime, None)
        self.assertAlmostEqual(step.value, 11.2, places=5)

        runtime.progression_event = ""
        step = tracker.step(runtime, None)

        runtime.progression_event = "level_complete"
        runtime.enemies_total = 27
        step = tracker.step(runtime, None)
        self.assertAlmostEqual(step.value, 29.6, places=5)

    def test_shoot_without_target_penalty_applies_after_grace_period(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            stationary_shoot_no_hit_cost=0.0,
            shoot_no_target_grace_ticks=3,
            shoot_no_target_cost=0.05,
            tile_discovery_reward=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }

        runtime.player_shoot_hold_active = True
        step1 = tracker.step(runtime, observation)
        self.assertAlmostEqual(step1.value, 0.0, places=6)

        step2 = tracker.step(runtime, observation)
        self.assertAlmostEqual(step2.value, 0.0, places=6)

        step3 = tracker.step(runtime, observation)
        self.assertAlmostEqual(step3.value, -0.05, places=6)

        step4 = tracker.step(runtime, observation)
        self.assertAlmostEqual(step4.value, -0.05, places=6)

    def test_tile_discovery_reward_for_new_tiles(self) -> None:
        cfg = RewardConfig(
            step_cost=0.0,
            look_at_enemy_reward=0.0,
            tile_discovery_reward=0.001,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)

        runtime.player_world_x = 5
        runtime.player_world_y = 5
        step1 = tracker.step(runtime, None)
        self.assertAlmostEqual(step1.value, 0.001, places=6)

        step2 = tracker.step(runtime, None)
        self.assertAlmostEqual(step2.value, 0.0, places=6)

        runtime.player_world_x = 35
        runtime.player_world_y = 5
        step3 = tracker.step(runtime, None)
        self.assertAlmostEqual(step3.value, 0.001, places=6)

        runtime.player_world_x = 5
        runtime.player_world_y = 35
        step4 = tracker.step(runtime, None)
        self.assertAlmostEqual(step4.value, 0.001, places=6)

    def test_default_reward_config_has_active_shooting_penalties(self) -> None:
        cfg = RewardConfig()
        self.assertGreater(cfg.stationary_shoot_no_hit_cost, 0.0)
        self.assertGreater(cfg.shoot_no_target_cost, 0.0)

    def test_reward_breakdown_sums_to_total(self) -> None:
        cfg = RewardConfig(
            step_cost=0.01,
            kill_reward=2.0,
            hit_reward=0.5,
            crate_reward=0.0,
            damage_cost=0.1,
            death_cost=0.0,
            look_at_enemy_reward=0.0,
            strafing_reward=0.0,
            idle_cost=0.0,
            stuck_cost=0.0,
            bad_shoot_cost=0.0,
            stationary_shoot_no_hit_cost=0.0,
            shoot_no_target_cost=0.0,
            tile_discovery_reward=0.0,
            visible_no_hit_cost=0.0,
        )
        tracker = RewardTracker(config=cfg)

        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.enemies_killed_by_player = 1
        runtime.player_hits_total = 2
        runtime.player_damage_taken_total = 3.0

        observation = {
            "rays": np.ones((32, 8), dtype=np.float32),
            "state": np.zeros((15,), dtype=np.float32),
        }
        step = tracker.step(runtime, observation)

        self.assertAlmostEqual(step.value, 2.69, places=6)
        self.assertAlmostEqual(sum(step.breakdown.values()), step.value, places=6)
        self.assertAlmostEqual(step.breakdown["step_cost"], -0.01, places=6)
        self.assertAlmostEqual(step.breakdown["kill_reward"], 2.0, places=6)
        self.assertAlmostEqual(step.breakdown["hit_reward"], 1.0, places=6)
        self.assertAlmostEqual(step.breakdown["damage_cost"], -0.3, places=6)


if __name__ == "__main__":
    unittest.main()
