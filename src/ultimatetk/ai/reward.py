from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ultimatetk.core.state import RuntimeState
from ultimatetk.rendering.constants import TILE_SIZE


@dataclass(frozen=True, slots=True)
class RewardConfig:
    step_cost: float = 0.0015

    kill_reward: float = 6.0
    hit_reward: float = 0.4
    crate_reward: float = 0.12
    damage_dealt_reward: float = 0.04

    damage_cost: float = 0.05
    death_cost: float = 15.0

    level_complete_reward_base: float = 10.0
    level_complete_reward_per_enemy: float = 1.0
    run_complete_reward: float = 30.0

    face_enemy_reward: float = 0.004
    aim_center_reward: float = 0.002
    alignment_improvement_reward: float = 0.015
    valid_shot_reward: float = 0.025

    tile_discovery_reward: float = 0.03
    frontier_tile_reward: float = 0.04

    inactivity_ticks_threshold: int = 60
    inactivity_cost: float = 0.015

    enemy_los_penalty_ticks: int = 80
    enemy_los_penalty_cost: float = 0.008

    stuck_ticks_threshold: int = 20
    stuck_radius_epsilon: float = 2.0
    stuck_cost: float = 0.02

    stationary_shoot_no_hit_cost: float = 0.015
    stationary_shoot_no_hit_grace_ticks: int = 5

    shoot_no_target_grace_ticks: int = 5
    shoot_no_target_cost: float = 0.02


_FRONT_SECTORS: set[int] = {0, 1, 31}
_RAY_SECTOR_COUNT: int = 32


@dataclass(frozen=True, slots=True)
class RewardStep:
    value: float
    inactivity_ticks: int
    breakdown: dict[str, float]


class RewardTracker:
    def __init__(self, config: RewardConfig | None = None) -> None:
        self._config = config or RewardConfig()
        self._penalty_scale: float = 1.0
        self._visited_tiles: set[tuple[int, int]] = set()
        self._reset(None)

    def set_penalty_scale(self, scale: float) -> None:
        self._penalty_scale = float(scale)

    def _reset(self, runtime: RuntimeState | None) -> None:
        if runtime is None:
            self._prev_kills = 0
            self._prev_hits = 0
            self._prev_crates = 0
            self._prev_damage_taken = 0.0
            self._prev_damage_dealt = 0.0
            self._prev_dead = False
            self._prev_progression_event = ""
            self._prev_shots_fired = 0
            self._prev_x = 0
            self._prev_y = 0
            self._prev_enemy_alignment = -1.0
            self._spawn_tile = (0, 0)
            self._max_tile_radius = 0
            self._stationary_shoot_ticks = 0
            self._inactivity_ticks = 0
            self._stuck_ticks = 0
            self._shoot_no_target_ticks = 0
            self._enemy_los_no_hit_ticks = 0
            self._visited_tiles.clear()
            return

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_damage_dealt = runtime.player_damage_dealt_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_shots_fired = runtime.player_shots_fired_total
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y
        self._prev_enemy_alignment = -1.0
        spawn_x = int(runtime.player_world_x) // TILE_SIZE
        spawn_y = int(runtime.player_world_y) // TILE_SIZE
        self._spawn_tile = (spawn_x, spawn_y)
        self._max_tile_radius = 0
        self._stationary_shoot_ticks = 0
        self._inactivity_ticks = 0
        self._stuck_ticks = 0
        self._shoot_no_target_ticks = 0
        self._enemy_los_no_hit_ticks = 0
        self._visited_tiles.clear()
        self._visited_tiles.add((spawn_x, spawn_y))

    def reset(self, runtime: RuntimeState | None) -> None:
        self._reset(runtime)

    def step(self, runtime: RuntimeState, observation: dict[str, Any] | None = None) -> RewardStep:
        cfg = self._config
        breakdown: dict[str, float] = {
            "step_cost": -cfg.step_cost * self._penalty_scale,
            "kill_reward": 0.0,
            "hit_reward": 0.0,
            "crate_reward": 0.0,
            "damage_dealt_reward": 0.0,
            "damage_cost": 0.0,
            "face_enemy_reward": 0.0,
            "aim_center_reward": 0.0,
            "alignment_improvement_reward": 0.0,
            "valid_shot_reward": 0.0,
            "level_complete_reward": 0.0,
            "run_complete_reward": 0.0,
            "death_cost": 0.0,
            "inactivity_cost": 0.0,
            "stuck_cost": 0.0,
            "stationary_shoot_no_hit_cost": 0.0,
            "shoot_no_target_cost": 0.0,
            "tile_discovery_reward": 0.0,
            "frontier_tile_reward": 0.0,
            "enemy_los_penalty": 0.0,
        }
        reward = breakdown["step_cost"]

        delta_kills = max(0, runtime.enemies_killed_by_player - self._prev_kills)
        delta_hits = max(0, runtime.player_hits_total - self._prev_hits)
        delta_crates = max(0, runtime.crates_collected_by_player - self._prev_crates)
        delta_shots = max(0, runtime.player_shots_fired_total - self._prev_shots_fired)
        delta_damage = max(0.0, runtime.player_damage_taken_total - self._prev_damage_taken)
        delta_damage_dealt = max(0.0, runtime.player_damage_dealt_total - self._prev_damage_dealt)
        shooting_active = runtime.player_shoot_hold_active or delta_shots > 0
        moved = abs(runtime.player_world_x - self._prev_x) + abs(runtime.player_world_y - self._prev_y)

        kill_delta = cfg.kill_reward * float(delta_kills)
        hit_delta = cfg.hit_reward * float(delta_hits)
        crate_delta = cfg.crate_reward * float(delta_crates)
        damage_delta = -cfg.damage_cost * float(delta_damage)
        damage_dealt_delta = cfg.damage_dealt_reward * delta_damage_dealt

        reward += kill_delta
        reward += hit_delta
        reward += crate_delta
        reward += damage_delta
        reward += damage_dealt_delta
        breakdown["kill_reward"] += kill_delta
        breakdown["hit_reward"] += hit_delta
        breakdown["crate_reward"] += crate_delta
        breakdown["damage_cost"] += damage_delta
        breakdown["damage_dealt_reward"] += damage_dealt_delta

        front, centered, alignment, enemy_visible = self._enemy_target_signal(observation)

        if front and not runtime.player_dead:
            reward += cfg.face_enemy_reward
            breakdown["face_enemy_reward"] += cfg.face_enemy_reward
            if centered:
                reward += cfg.aim_center_reward
                breakdown["aim_center_reward"] += cfg.aim_center_reward

        if not enemy_visible:
            self._prev_enemy_alignment = -1.0
        elif self._prev_enemy_alignment >= 0.0 and alignment > self._prev_enemy_alignment + 0.001 and not runtime.player_dead:
            alignment_delta = alignment - self._prev_enemy_alignment
            reward += alignment_delta * cfg.alignment_improvement_reward
            breakdown["alignment_improvement_reward"] += alignment_delta * cfg.alignment_improvement_reward

        if delta_shots > 0 and front and not runtime.player_dead:
            valid_shots = float(delta_shots)
            reward += valid_shots * cfg.valid_shot_reward
            breakdown["valid_shot_reward"] += valid_shots * cfg.valid_shot_reward

        progression_changed = runtime.progression_event != self._prev_progression_event
        if progression_changed and runtime.progression_event == "level_complete":
            scaled_level_reward = cfg.level_complete_reward_base + max(0, runtime.enemies_total) * cfg.level_complete_reward_per_enemy
            reward += scaled_level_reward
            breakdown["level_complete_reward"] += scaled_level_reward
        if progression_changed and runtime.progression_event == "run_complete":
            reward += cfg.run_complete_reward
            breakdown["run_complete_reward"] += cfg.run_complete_reward

        if runtime.player_dead and not self._prev_dead:
            reward -= cfg.death_cost
            breakdown["death_cost"] -= cfg.death_cost

        exploration_event = False
        if not runtime.player_dead:
            player_tile_x = int(runtime.player_world_x) // TILE_SIZE
            player_tile_y = int(runtime.player_world_y) // TILE_SIZE
            current_tile = (player_tile_x, player_tile_y)

            if current_tile not in self._visited_tiles:
                self._visited_tiles.add(current_tile)
                reward += cfg.tile_discovery_reward
                breakdown["tile_discovery_reward"] += cfg.tile_discovery_reward
                exploration_event = True

                radius = max(abs(player_tile_x - self._spawn_tile[0]), abs(player_tile_y - self._spawn_tile[1]))
                if radius > self._max_tile_radius:
                    self._max_tile_radius = radius
                    reward += cfg.frontier_tile_reward
                    breakdown["frontier_tile_reward"] += cfg.frontier_tile_reward

        combat_progress = (
            delta_hits > 0
            or delta_kills > 0
            or delta_damage_dealt > 0.0
            or (delta_shots > 0 and front)
        )
        valid_engagement = exploration_event or combat_progress

        if runtime.player_dead or valid_engagement:
            self._inactivity_ticks = 0
        else:
            self._inactivity_ticks += 1
            if self._inactivity_ticks >= cfg.inactivity_ticks_threshold:
                reward -= cfg.inactivity_cost * self._penalty_scale
                breakdown["inactivity_cost"] -= cfg.inactivity_cost * self._penalty_scale

        if progression_changed or runtime.player_dead:
            self._stuck_ticks = 0
        elif not shooting_active and moved <= cfg.stuck_radius_epsilon:
            self._stuck_ticks += 1
            if self._stuck_ticks >= cfg.stuck_ticks_threshold:
                reward -= cfg.stuck_cost * self._penalty_scale
                breakdown["stuck_cost"] -= cfg.stuck_cost * self._penalty_scale
        else:
            self._stuck_ticks = 0

        if delta_hits > 0:
            self._stationary_shoot_ticks = 0
        elif not runtime.player_dead and shooting_active and moved <= cfg.stuck_radius_epsilon:
            self._stationary_shoot_ticks += 1
            if self._stationary_shoot_ticks >= cfg.stationary_shoot_no_hit_grace_ticks:
                reward -= cfg.stationary_shoot_no_hit_cost * self._penalty_scale
                breakdown["stationary_shoot_no_hit_cost"] -= cfg.stationary_shoot_no_hit_cost * self._penalty_scale
        else:
            self._stationary_shoot_ticks = 0

        if not runtime.player_dead and shooting_active and not front:
            self._shoot_no_target_ticks += 1
            if self._shoot_no_target_ticks >= cfg.shoot_no_target_grace_ticks:
                reward -= cfg.shoot_no_target_cost * self._penalty_scale
                breakdown["shoot_no_target_cost"] -= cfg.shoot_no_target_cost * self._penalty_scale
        else:
            self._shoot_no_target_ticks = 0

        if delta_hits > 0:
            self._enemy_los_no_hit_ticks = 0
        elif front and not runtime.player_dead:
            self._enemy_los_no_hit_ticks += 1
            if self._enemy_los_no_hit_ticks >= cfg.enemy_los_penalty_ticks:
                reward -= cfg.enemy_los_penalty_cost * self._penalty_scale
                breakdown["enemy_los_penalty"] -= cfg.enemy_los_penalty_cost * self._penalty_scale
        else:
            self._enemy_los_no_hit_ticks = 0

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_damage_dealt = runtime.player_damage_dealt_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_shots_fired = runtime.player_shots_fired_total
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y
        self._prev_enemy_alignment = alignment if enemy_visible else -1.0

        return RewardStep(value=reward, inactivity_ticks=self._inactivity_ticks, breakdown=breakdown)

    @staticmethod
    def _enemy_target_signal(observation: dict[str, Any] | None) -> tuple[bool, bool, float, bool]:
        if not observation:
            return False, False, 0.0, False
        rays = observation.get("rays")
        if rays is None:
            return False, False, 0.0, False

        matrix = np.asarray(rays, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] < 2 or matrix.shape[0] < _RAY_SECTOR_COUNT:
            return False, False, 0.0, False

        enemy_dists = matrix[:_RAY_SECTOR_COUNT, 1]
        visible_mask = enemy_dists < 1.0
        any_visible = bool(np.any(visible_mask))
        if not any_visible:
            return False, False, 0.0, False

        front = bool(np.any(visible_mask[0])) or bool(np.any(visible_mask[1])) or bool(np.any(visible_mask[31]))
        centered = bool(visible_mask[0])

        nearest_sector = int(np.argmin(enemy_dists))
        sector_offset = min(nearest_sector, _RAY_SECTOR_COUNT - nearest_sector)
        alignment = 1.0 - (float(sector_offset) / 16.0)

        return front, centered, max(0.0, alignment), True
