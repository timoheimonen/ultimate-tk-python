from __future__ import annotations

import sys
from pathlib import Path
import unittest
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.reward import RewardConfig, RewardTracker
from ultimatetk.core.state import RuntimeState


def _test_cfg(**overrides: Any) -> RewardConfig:
    base: dict[str, Any] = {
        "step_cost": 0.0,
        "kill_reward": 0.0,
        "hit_reward": 0.0,
        "crate_reward": 0.0,
        "damage_dealt_reward": 0.0,
        "damage_cost": 0.0,
        "death_cost": 0.0,
        "level_complete_reward_base": 0.0,
        "level_complete_reward_per_enemy": 0.0,
        "run_complete_reward": 0.0,
        "face_enemy_reward": 0.0,
        "aim_center_reward": 0.0,
        "alignment_improvement_reward": 0.0,
        "valid_shot_reward": 0.0,
        "tile_discovery_reward": 0.0,
        "frontier_tile_reward": 0.0,
        "inactivity_ticks_threshold": 999_999,
        "inactivity_cost": 0.0,
        "enemy_los_penalty_ticks": 999_999,
        "enemy_los_penalty_cost": 0.0,
        "stuck_ticks_threshold": 999_999,
        "stuck_radius_epsilon": 0.0,
        "stuck_cost": 0.0,
        "stationary_shoot_no_hit_cost": 0.0,
        "stationary_shoot_no_hit_grace_ticks": 999_999,
        "shoot_no_target_grace_ticks": 999_999,
        "shoot_no_target_cost": 0.0,
    }
    base.update(overrides)
    return RewardConfig(**base)


class GymRewardTests(unittest.TestCase):
    # -- Engagement (face / center) --

    def test_face_enemy_reward_when_enemy_in_front_sector_0(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=0))
        self.assertAlmostEqual(step.value, 0.004, places=6)
        self.assertAlmostEqual(step.breakdown["face_enemy_reward"], 0.004, places=6)

    def test_face_enemy_reward_when_enemy_in_front_sector_1(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=1))
        self.assertAlmostEqual(step.value, 0.004, places=6)

    def test_face_enemy_reward_when_enemy_in_front_sector_31(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=31))
        self.assertAlmostEqual(step.value, 0.004, places=6)

    def test_aim_center_reward_additive_to_face(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004, aim_center_reward=0.002))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=0))
        self.assertAlmostEqual(step.value, 0.006, places=6)
        self.assertAlmostEqual(step.breakdown["face_enemy_reward"], 0.004, places=6)
        self.assertAlmostEqual(step.breakdown["aim_center_reward"], 0.002, places=6)

    def test_no_face_reward_when_enemy_side(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=4))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_no_face_reward_when_enemy_behind(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=16))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_no_face_reward_when_no_enemy_visible(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(no_enemy=True))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_face_reward_when_enemy_in_front_despite_closer_side_enemy(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004, valid_shot_reward=0.025))
        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shots_fired_total = 1

        obs = _make_observation(enemy_sector=4, extra_enemies={0: 0.6})

        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.breakdown["face_enemy_reward"], 0.004, places=6)
        self.assertAlmostEqual(step.breakdown["valid_shot_reward"], 0.025, places=6)
        self.assertAlmostEqual(step.breakdown["shoot_no_target_cost"], 0.0, places=6)

    def test_no_face_reward_when_front_enemy_is_stale_but_side_enemy_is_closest(self) -> None:
        cfg = RewardConfig(
            face_enemy_reward=0.004,
            aim_center_reward=0.0,
            alignment_improvement_reward=0.0,
            valid_shot_reward=0.0,
            tile_discovery_reward=0.0,
            step_cost=0.0,
        )
        tracker = RewardTracker(config=cfg)
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(enemy_sector=4, extra_enemies={0: 0.6})

        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.breakdown["face_enemy_reward"], 0.004, places=6)


    # -- Valid shot reward --

    def test_valid_shot_reward_when_enemy_in_front(self) -> None:
        tracker = RewardTracker(config=_test_cfg(valid_shot_reward=0.025))
        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shots_fired_total = 1

        step = tracker.step(runtime, _make_observation(enemy_sector=0))
        self.assertAlmostEqual(step.value, 0.025, places=6)
        self.assertAlmostEqual(step.breakdown["valid_shot_reward"], 0.025, places=6)

    def test_no_valid_shot_reward_when_enemy_side(self) -> None:
        tracker = RewardTracker(config=_test_cfg(valid_shot_reward=0.025))
        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shots_fired_total = 1

        step = tracker.step(runtime, _make_observation(enemy_sector=4))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    def test_no_valid_shot_reward_when_no_shots_fired(self) -> None:
        tracker = RewardTracker(config=_test_cfg(valid_shot_reward=0.025))
        runtime = RuntimeState()
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=0))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    # -- Alignment improvement reward --

    def test_alignment_improvement_reward(self) -> None:
        tracker = RewardTracker(config=_test_cfg(alignment_improvement_reward=0.015))
        runtime = RuntimeState()
        tracker.reset(runtime)

        tracker.step(runtime, _make_observation(enemy_sector=8))
        step = tracker.step(runtime, _make_observation(enemy_sector=2))

        expected_alignment_8 = 1.0 - (8.0 / 16.0)
        expected_alignment_2 = 1.0 - (2.0 / 16.0)
        delta = expected_alignment_2 - expected_alignment_8
        expected_reward = delta * 0.015

        self.assertAlmostEqual(step.breakdown["alignment_improvement_reward"], expected_reward, places=6)

    def test_no_alignment_reward_when_alignment_worsens(self) -> None:
        tracker = RewardTracker(config=_test_cfg(alignment_improvement_reward=0.015))
        runtime = RuntimeState()
        tracker.reset(runtime)

        tracker.step(runtime, _make_observation(enemy_sector=2))
        step = tracker.step(runtime, _make_observation(enemy_sector=8))

        self.assertAlmostEqual(step.breakdown["alignment_improvement_reward"], 0.0, places=6)

    # -- Face + center do not trigger when dead --

    def test_no_face_reward_when_dead(self) -> None:
        tracker = RewardTracker(config=_test_cfg(face_enemy_reward=0.004, aim_center_reward=0.002))
        runtime = RuntimeState()
        runtime.player_dead = True
        tracker.reset(runtime)

        step = tracker.step(runtime, _make_observation(enemy_sector=0))
        self.assertAlmostEqual(step.value, 0.0, places=6)

    # -- Inactivity penalty --

    def test_inactivity_penalty_after_threshold(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=3, inactivity_cost=1.0))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        tracker.step(runtime, obs)
        tracker.step(runtime, obs)
        step3 = tracker.step(runtime, obs)
        step4 = tracker.step(runtime, obs)

        self.assertAlmostEqual(step3.value, -1.0, places=6)
        self.assertAlmostEqual(step4.value, -1.0, places=6)

    def test_inactivity_reset_on_tile_discovery(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            inactivity_ticks_threshold=3, inactivity_cost=1.0, tile_discovery_reward=0.03,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_world_x = 0
        runtime.player_world_y = 0
        tracker.step(runtime, obs)
        tracker.step(runtime, obs)

        runtime.player_world_x = 32
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)

        self.assertAlmostEqual(step.value, 0.03, places=6)
        self.assertAlmostEqual(step.breakdown["inactivity_cost"], 0.0, places=6)

    def test_inactivity_reset_on_hit(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=3, inactivity_cost=1.0))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_world_x = 1
        runtime.player_world_y = 0
        tracker.step(runtime, obs)
        runtime.player_world_x = 2
        runtime.player_world_y = 0
        tracker.step(runtime, obs)

        runtime.player_hits_total = 1
        runtime.player_world_x = 3
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.breakdown["inactivity_cost"], 0.0, places=6)

    def test_inactivity_reset_on_valid_shot(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=3, inactivity_cost=1.0))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        obs_front = _make_observation(enemy_sector=0)

        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_world_x = 1
        runtime.player_world_y = 0
        tracker.step(runtime, obs)
        runtime.player_world_x = 2
        runtime.player_world_y = 0
        tracker.step(runtime, obs)

        runtime.player_shots_fired_total = 1
        runtime.player_world_x = 3
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs_front)
        self.assertAlmostEqual(step.breakdown["inactivity_cost"], 0.0, places=6)

    def test_inactivity_reset_on_kill(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=3, inactivity_cost=1.0))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_world_x = 1
        runtime.player_world_y = 0
        tracker.step(runtime, obs)
        runtime.player_world_x = 2
        runtime.player_world_y = 0
        tracker.step(runtime, obs)

        runtime.enemies_killed_by_player = 1
        runtime.player_world_x = 3
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.breakdown["inactivity_cost"], 0.0, places=6)

    # -- Stationary shoot no hit penalty --

    def test_stationary_shooting_without_hits_gets_penalty_after_grace(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            stationary_shoot_no_hit_cost=0.25,
            stationary_shoot_no_hit_grace_ticks=2,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_shoot_hold_active = True

        first = tracker.step(runtime, obs)
        second = tracker.step(runtime, obs)
        third = tracker.step(runtime, obs)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, -0.25, places=6)
        self.assertAlmostEqual(third.value, -0.25, places=6)

    def test_stationary_shooting_penalty_resets_when_hit_occurs(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            hit_reward=0.4,
            stationary_shoot_no_hit_cost=0.25,
            stationary_shoot_no_hit_grace_ticks=2,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_shoot_hold_active = True

        first = tracker.step(runtime, obs)
        runtime.player_hits_total = 1
        second = tracker.step(runtime, obs)
        third = tracker.step(runtime, obs)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, 0.4, places=6)
        self.assertAlmostEqual(third.value, 0.0, places=6)

    # -- Stuck penalty --

    def test_stuck_cost_applies_when_trapped_in_small_area(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            stuck_ticks_threshold=2, stuck_radius_epsilon=2.0, stuck_cost=0.4,
        ))
        runtime = RuntimeState()
        runtime.player_world_x = 10
        runtime.player_world_y = 10
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        first = tracker.step(runtime, obs)
        runtime.player_world_x = 11
        runtime.player_world_y = 10
        second = tracker.step(runtime, obs)
        runtime.player_world_x = 10
        runtime.player_world_y = 11
        third = tracker.step(runtime, obs)

        self.assertAlmostEqual(first.value, 0.0, places=6)
        self.assertAlmostEqual(second.value, -0.4, places=6)
        self.assertAlmostEqual(third.value, -0.4, places=6)

    def test_stuck_counter_resets_after_real_movement(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            stuck_ticks_threshold=2, stuck_radius_epsilon=2.0, stuck_cost=0.4,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        tracker.step(runtime, obs)
        second = tracker.step(runtime, obs)
        self.assertAlmostEqual(second.value, -0.4, places=6)

        runtime.player_world_x = 20
        moved = tracker.step(runtime, obs)
        self.assertAlmostEqual(moved.value, 0.0, places=6)

        runtime.player_world_x = 20
        stationary_again = tracker.step(runtime, obs)
        self.assertAlmostEqual(stationary_again.value, 0.0, places=6)

    def test_stuck_counter_resets_while_shooting_active(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            stuck_ticks_threshold=2, stuck_radius_epsilon=2.0, stuck_cost=0.4,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        tracker.step(runtime, obs)
        second = tracker.step(runtime, obs)
        self.assertAlmostEqual(second.value, -0.4, places=6)

        runtime.player_shoot_hold_active = True
        shooting = tracker.step(runtime, obs)
        self.assertAlmostEqual(shooting.value, 0.0, places=6)

        runtime.player_shoot_hold_active = False
        after_release = tracker.step(runtime, obs)
        self.assertAlmostEqual(after_release.value, 0.0, places=6)

    # -- Level complete --

    def test_level_complete_reward_scales_by_enemy_count(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            level_complete_reward_base=10.0, level_complete_reward_per_enemy=1.0,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.progression_event = "level_complete"
        runtime.enemies_total = 4
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.value, 14.0, places=5)

        runtime.progression_event = ""
        tracker.step(runtime, obs)

        runtime.progression_event = "level_complete"
        runtime.enemies_total = 27
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.value, 37.0, places=5)

    # -- Shoot no target penalty (front-based) --

    def test_shoot_without_front_target_penalty_after_grace(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            shoot_no_target_grace_ticks=3, shoot_no_target_cost=0.05,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(enemy_sector=4)

        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_shoot_hold_active = True

        step1 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step1.value, 0.0, places=6)

        step2 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step2.value, 0.0, places=6)

        step3 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step3.value, -0.05, places=6)

        step4 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step4.value, -0.05, places=6)

    def test_shoot_no_target_suppressed_when_enemy_in_front(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            shoot_no_target_grace_ticks=2, shoot_no_target_cost=0.05,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)
        runtime.player_shoot_hold_active = True

        obs_front = _make_observation(enemy_sector=0)
        _consume_spawn_tile(tracker, runtime, obs_front)

        step1 = tracker.step(runtime, obs_front)
        step2 = tracker.step(runtime, obs_front)
        step3 = tracker.step(runtime, obs_front)

        self.assertAlmostEqual(step1.breakdown["shoot_no_target_cost"], 0.0, places=6)
        self.assertAlmostEqual(step2.breakdown["shoot_no_target_cost"], 0.0, places=6)
        self.assertAlmostEqual(step3.breakdown["shoot_no_target_cost"], 0.0, places=6)

    # -- Tile discovery & frontier --

    def test_tile_discovery_reward_for_new_tiles(self) -> None:
        tracker = RewardTracker(config=_test_cfg(tile_discovery_reward=0.03))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        runtime.player_world_x = 0
        runtime.player_world_y = 0
        tracker.step(runtime, obs)

        runtime.player_world_x = 33
        runtime.player_world_y = 0
        step1 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step1.value, 0.03, places=6)

        step2 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step2.value, 0.0, places=6)

        runtime.player_world_x = 65
        runtime.player_world_y = 0
        step3 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step3.value, 0.03, places=6)

        runtime.player_world_x = 33
        runtime.player_world_y = 33
        step4 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step4.value, 0.03, places=6)

    def test_frontier_tile_reward_for_furthest_tile_from_spawn(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            tile_discovery_reward=0.03, frontier_tile_reward=0.04,
        ))
        runtime = RuntimeState()
        runtime.player_world_x = 32
        runtime.player_world_y = 32
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        runtime.player_world_x = 64
        runtime.player_world_y = 32
        step1 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step1.value, 0.07, places=6)
        self.assertAlmostEqual(step1.breakdown["tile_discovery_reward"], 0.03, places=6)
        self.assertAlmostEqual(step1.breakdown["frontier_tile_reward"], 0.04, places=6)

        runtime.player_world_x = 96
        runtime.player_world_y = 64
        step2 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step2.breakdown["frontier_tile_reward"], 0.04, places=6)

    def test_frontier_tile_only_when_radius_exceeds_max(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            tile_discovery_reward=0.03, frontier_tile_reward=0.04,
        ))
        runtime = RuntimeState()
        runtime.player_world_x = 0
        runtime.player_world_y = 0
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        runtime.player_world_x = 64
        runtime.player_world_y = 0
        tracker.step(runtime, obs)

        runtime.player_world_x = 32
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)

        self.assertAlmostEqual(step.breakdown["tile_discovery_reward"], 0.03, places=6)
        self.assertAlmostEqual(step.breakdown["frontier_tile_reward"], 0.0, places=6)

    # -- Enemy LOS penalty --

    def test_enemy_los_penalty_after_threshold(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            enemy_los_penalty_ticks=3, enemy_los_penalty_cost=0.1,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(enemy_sector=0)
        _consume_spawn_tile(tracker, runtime, obs)

        tracker.step(runtime, obs)
        tracker.step(runtime, obs)
        step3 = tracker.step(runtime, obs)
        step4 = tracker.step(runtime, obs)

        self.assertAlmostEqual(step3.value, -0.1, places=6)
        self.assertAlmostEqual(step4.value, -0.1, places=6)

    def test_enemy_los_penalty_resets_on_hit(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            hit_reward=0.4, enemy_los_penalty_ticks=2, enemy_los_penalty_cost=0.1,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(enemy_sector=0)
        _consume_spawn_tile(tracker, runtime, obs)

        tracker.step(runtime, obs)
        runtime.player_hits_total = 1
        step2 = tracker.step(runtime, obs)
        step3 = tracker.step(runtime, obs)

        self.assertAlmostEqual(step2.value, 0.4, places=6)
        self.assertAlmostEqual(step2.breakdown["enemy_los_penalty"], 0.0, places=6)
        self.assertAlmostEqual(step3.breakdown["enemy_los_penalty"], 0.0, places=6)

    def test_enemy_los_penalty_only_when_enemy_in_front(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            enemy_los_penalty_ticks=2, enemy_los_penalty_cost=0.1,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs_side = _make_observation(enemy_sector=8)
        _consume_spawn_tile(tracker, runtime, obs_side)

        tracker.step(runtime, obs_side)
        tracker.step(runtime, obs_side)
        step3 = tracker.step(runtime, obs_side)

        self.assertAlmostEqual(step3.breakdown["enemy_los_penalty"], 0.0, places=6)

    # -- Default config checks --

    def test_default_config_has_active_penalties(self) -> None:
        cfg = RewardConfig()
        self.assertGreater(cfg.stationary_shoot_no_hit_cost, 0.0)
        self.assertGreater(cfg.shoot_no_target_cost, 0.0)
        self.assertGreater(cfg.inactivity_cost, 0.0)
        self.assertGreater(cfg.enemy_los_penalty_cost, 0.0)

    def test_default_config_values(self) -> None:
        cfg = RewardConfig()
        self.assertAlmostEqual(cfg.step_cost, 0.0015, places=6)
        self.assertAlmostEqual(cfg.kill_reward, 6.0, places=6)
        self.assertAlmostEqual(cfg.hit_reward, 0.4, places=6)
        self.assertAlmostEqual(cfg.damage_cost, 0.05, places=6)
        self.assertAlmostEqual(cfg.death_cost, 15.0, places=6)
        self.assertAlmostEqual(cfg.level_complete_reward_base, 10.0, places=6)
        self.assertAlmostEqual(cfg.level_complete_reward_per_enemy, 1.0, places=6)
        self.assertAlmostEqual(cfg.run_complete_reward, 30.0, places=6)
        self.assertAlmostEqual(cfg.face_enemy_reward, 0.004, places=6)
        self.assertAlmostEqual(cfg.aim_center_reward, 0.002, places=6)
        self.assertAlmostEqual(cfg.alignment_improvement_reward, 0.015, places=6)
        self.assertAlmostEqual(cfg.valid_shot_reward, 0.025, places=6)
        self.assertAlmostEqual(cfg.tile_discovery_reward, 0.03, places=6)
        self.assertAlmostEqual(cfg.frontier_tile_reward, 0.04, places=6)
        self.assertAlmostEqual(cfg.inactivity_ticks_threshold, 60, places=6)
        self.assertAlmostEqual(cfg.inactivity_cost, 0.015, places=6)
        self.assertAlmostEqual(cfg.enemy_los_penalty_ticks, 80, places=6)
        self.assertAlmostEqual(cfg.enemy_los_penalty_cost, 0.008, places=6)
        self.assertAlmostEqual(cfg.damage_dealt_reward, 0.04, places=6)

    # -- Breakdown sum --

    def test_reward_breakdown_sums_to_total(self) -> None:
        tracker = RewardTracker(config=_test_cfg(
            step_cost=0.01, kill_reward=2.0, hit_reward=0.5, crate_reward=1.0, damage_cost=0.1,
        ))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.enemies_killed_by_player = 1
        runtime.player_hits_total = 2
        runtime.player_damage_taken_total = 3.0
        runtime.crates_collected_by_player = 1
        runtime.player_world_x = 1
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)

        self.assertAlmostEqual(step.value, 3.69, places=6)
        self.assertAlmostEqual(sum(step.breakdown.values()), step.value, places=6)
        self.assertAlmostEqual(step.breakdown["step_cost"], -0.01, places=6)
        self.assertAlmostEqual(step.breakdown["kill_reward"], 2.0, places=6)
        self.assertAlmostEqual(step.breakdown["hit_reward"], 1.0, places=6)
        self.assertAlmostEqual(step.breakdown["damage_cost"], -0.3, places=6)
        self.assertAlmostEqual(step.breakdown["crate_reward"], 1.0, places=6)

    # -- Damage dealt --

    def test_damage_dealt_reward_from_delta(self) -> None:
        tracker = RewardTracker(config=_test_cfg(damage_dealt_reward=0.04))
        runtime = RuntimeState()
        runtime.player_damage_dealt_total = 0.0
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_damage_dealt_total = 10.0
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.value, 0.4, places=6)
        self.assertAlmostEqual(step.breakdown["damage_dealt_reward"], 0.4, places=6)

        runtime.player_damage_dealt_total = 25.0
        step2 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step2.value, 0.6, places=6)

    # -- Penalty scale --

    def test_penalty_scale_reduces_step_cost(self) -> None:
        tracker = RewardTracker(config=_test_cfg(step_cost=0.01))
        tracker.set_penalty_scale(0.25)

        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.value, -0.0025, places=6)

    def test_penalty_scale_reduces_inactivity_cost(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=3, inactivity_cost=0.2))
        tracker.set_penalty_scale(0.5)

        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        first = tracker.step(runtime, obs)
        self.assertAlmostEqual(first.value, 0.0, places=6)

        second = tracker.step(runtime, obs)
        self.assertAlmostEqual(second.value, 0.0, places=6)

        third = tracker.step(runtime, obs)
        self.assertAlmostEqual(third.value, -0.1, places=6)

    def test_penalty_scale_does_not_affect_rewards(self) -> None:
        tracker = RewardTracker(config=_test_cfg(kill_reward=5.0, hit_reward=0.5))
        tracker.set_penalty_scale(0.1)

        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.enemies_killed_by_player = 1
        runtime.player_world_x = 1
        runtime.player_world_y = 0
        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.breakdown["kill_reward"], 5.0, places=6)

    def test_set_penalty_scale_clamps_to_float(self) -> None:
        tracker = RewardTracker()
        tracker.set_penalty_scale(0)
        self.assertEqual(tracker._penalty_scale, 0.0)
        tracker.set_penalty_scale(2.5)
        self.assertEqual(tracker._penalty_scale, 2.5)

    def test_damage_dealt_zero_when_no_damage_dealt(self) -> None:
        tracker = RewardTracker(config=_test_cfg(damage_dealt_reward=0.04))
        runtime = RuntimeState()
        runtime.player_damage_dealt_total = 0.0
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        step = tracker.step(runtime, obs)
        self.assertAlmostEqual(step.value, 0.0, places=6)
        self.assertAlmostEqual(step.breakdown["damage_dealt_reward"], 0.0, places=6)

    # -- inactivity_ticks field --

    def test_inactivity_ticks_reflects_counter(self) -> None:
        tracker = RewardTracker(config=_test_cfg(inactivity_ticks_threshold=999, inactivity_cost=0.0))
        runtime = RuntimeState()
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)

        step1 = tracker.step(runtime, obs)
        step2 = tracker.step(runtime, obs)
        step3 = tracker.step(runtime, obs)

        self.assertEqual(step1.inactivity_ticks, 1)
        self.assertEqual(step2.inactivity_ticks, 2)
        self.assertEqual(step3.inactivity_ticks, 3)

    # -- Death reward suppression --

    def test_death_cost_applied_once(self) -> None:
        tracker = RewardTracker(config=_test_cfg(death_cost=15.0))
        runtime = RuntimeState()
        runtime.player_dead = False
        tracker.reset(runtime)

        obs = _make_observation(no_enemy=True)
        _consume_spawn_tile(tracker, runtime, obs)

        runtime.player_dead = True
        step1 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step1.value, -15.0, places=6)

        step2 = tracker.step(runtime, obs)
        self.assertAlmostEqual(step2.value, 0.0, places=6)


def _make_observation(
    enemy_sector: int | None = None,
    no_enemy: bool = False,
    extra_enemies: dict[int, float] | None = None,
) -> dict:
    rays = np.ones((32, 8), dtype=np.float32)
    if not no_enemy and enemy_sector is not None:
        rays[enemy_sector, 1] = 0.4
    if extra_enemies:
        for sector, dist in extra_enemies.items():
            rays[sector, 1] = dist
    return {
        "rays": rays,
        "state": np.zeros((15,), dtype=np.float32),
    }


def _consume_spawn_tile(tracker: RewardTracker, runtime: RuntimeState, obs: dict) -> None:
    tracker.step(runtime, obs)
