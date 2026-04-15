from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ultimatetk.core.state import RuntimeState
from ultimatetk.rendering.constants import TILE_SIZE


@dataclass(frozen=True, slots=True)
class RewardConfig:
    step_cost: float = 0.001

    kill_reward: float = 5.0
    hit_reward: float = 0.5
    crate_reward: float = 0.15

    damage_cost: float = 0.04
    death_cost: float = 12.0

    level_complete_reward_base: float = 8.0
    level_complete_reward_per_enemy: float = 0.8
    run_complete_reward: float = 40.0

    look_at_enemy_reward: float = 0.003
    strafing_reward: float = 0.003

    idle_ticks_threshold: int = 120
    idle_cost: float = 0.2
    idle_distance_epsilon: float = 2.0

    stationary_shoot_no_hit_cost: float = 0.01
    stationary_shoot_no_hit_grace_ticks: int = 4

    stuck_ticks_threshold: int = 20
    stuck_radius_epsilon: float = 2.0
    stuck_cost: float = 0.02

    bad_shoot_ticks_threshold: int = 20
    bad_shoot_cost: float = 0.02

    shoot_no_target_grace_ticks: int = 5
    shoot_no_target_cost: float = 0.015

    tile_discovery_reward: float = 0.001

    visible_no_hit_ticks_threshold: int = 100
    visible_no_hit_cost: float = 0.004


@dataclass(frozen=True, slots=True)
class RewardStep:
    value: float
    stationary_ticks: int
    breakdown: dict[str, float]


class RewardTracker:
    def __init__(self, config: RewardConfig | None = None) -> None:
        self._config = config or RewardConfig()
        self._visited_tiles: set[tuple[int, int]] = set()
        self._reset(None)

    def _reset(self, runtime: RuntimeState | None) -> None:
        if runtime is None:
            self._prev_kills = 0
            self._prev_hits = 0
            self._prev_crates = 0
            self._prev_damage_taken = 0.0
            self._prev_dead = False
            self._prev_progression_event = ""
            self._prev_shots_fired = 0
            self._prev_x = 0
            self._prev_y = 0
            self._stationary_ticks = 0
            self._bad_shoot_ticks = 0
            self._stationary_shoot_ticks = 0
            self._visible_no_hit_ticks = 0
            self._shoot_no_target_ticks = 0
            self._idle_ticks = 0
            self._stuck_ticks = 0
            self._visited_tiles.clear()
            return

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_shots_fired = runtime.player_shots_fired_total
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y
        self._stationary_ticks = 0
        self._bad_shoot_ticks = 0
        self._stationary_shoot_ticks = 0
        self._visible_no_hit_ticks = 0
        self._shoot_no_target_ticks = 0
        self._idle_ticks = 0
        self._stuck_ticks = 0
        self._visited_tiles.clear()

    def reset(self, runtime: RuntimeState | None) -> None:
        self._reset(runtime)

    def step(self, runtime: RuntimeState, observation: dict[str, Any] | None = None) -> RewardStep:
        cfg = self._config
        breakdown: dict[str, float] = {
            "step_cost": -cfg.step_cost,
            "kill_reward": 0.0,
            "hit_reward": 0.0,
            "crate_reward": 0.0,
            "damage_cost": 0.0,
            "look_at_enemy_reward": 0.0,
            "visible_no_hit_cost": 0.0,
            "strafing_reward": 0.0,
            "level_complete_reward": 0.0,
            "run_complete_reward": 0.0,
            "death_cost": 0.0,
            "idle_cost": 0.0,
            "stuck_cost": 0.0,
            "bad_shoot_cost": 0.0,
            "stationary_shoot_no_hit_cost": 0.0,
            "shoot_no_target_cost": 0.0,
            "tile_discovery_reward": 0.0,
        }
        reward = breakdown["step_cost"]

        delta_kills = max(0, runtime.enemies_killed_by_player - self._prev_kills)
        delta_hits = max(0, runtime.player_hits_total - self._prev_hits)
        delta_crates = max(0, runtime.crates_collected_by_player - self._prev_crates)
        delta_shots = max(0, runtime.player_shots_fired_total - self._prev_shots_fired)
        delta_damage = max(0.0, runtime.player_damage_taken_total - self._prev_damage_taken)
        shooting_active = runtime.player_shoot_hold_active or delta_shots > 0

        kill_delta = cfg.kill_reward * float(delta_kills)
        hit_delta = cfg.hit_reward * float(delta_hits)
        crate_delta = cfg.crate_reward * float(delta_crates)
        damage_delta = -cfg.damage_cost * float(delta_damage)
        reward += kill_delta
        reward += hit_delta
        reward += crate_delta
        reward += damage_delta
        breakdown["kill_reward"] += kill_delta
        breakdown["hit_reward"] += hit_delta
        breakdown["crate_reward"] += crate_delta
        breakdown["damage_cost"] += damage_delta

        enemy_visible = self._enemy_visible(observation)

        if enemy_visible and not runtime.player_dead:
            reward += cfg.look_at_enemy_reward
            breakdown["look_at_enemy_reward"] += cfg.look_at_enemy_reward
            self._visible_no_hit_ticks += 1
            if self._visible_no_hit_ticks >= cfg.visible_no_hit_ticks_threshold:
                reward -= cfg.visible_no_hit_cost
                breakdown["visible_no_hit_cost"] -= cfg.visible_no_hit_cost
        else:
            self._visible_no_hit_ticks = 0

        if enemy_visible and self._player_strafing(observation) and not runtime.player_dead:
            reward += cfg.strafing_reward
            breakdown["strafing_reward"] += cfg.strafing_reward

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

        moved = abs(runtime.player_world_x - self._prev_x) + abs(runtime.player_world_y - self._prev_y)

        if not shooting_active and not runtime.player_dead and moved <= cfg.idle_distance_epsilon:
            self._idle_ticks += 1
            if self._idle_ticks >= cfg.idle_ticks_threshold:
                reward -= cfg.idle_cost
                breakdown["idle_cost"] -= cfg.idle_cost
        else:
            self._idle_ticks = 0

        if progression_changed or runtime.player_dead:
            self._stuck_ticks = 0
        elif not shooting_active and moved <= cfg.stuck_radius_epsilon:
            self._stuck_ticks += 1
            if self._stuck_ticks >= cfg.stuck_ticks_threshold:
                reward -= cfg.stuck_cost
                breakdown["stuck_cost"] -= cfg.stuck_cost
        else:
            self._stuck_ticks = 0

        if not runtime.player_dead and shooting_active and delta_hits == 0 and not enemy_visible:
            self._bad_shoot_ticks += 1
            if self._bad_shoot_ticks >= cfg.bad_shoot_ticks_threshold:
                reward -= cfg.bad_shoot_cost
                breakdown["bad_shoot_cost"] -= cfg.bad_shoot_cost
        else:
            self._bad_shoot_ticks = 0

        if delta_hits > 0:
            self._stationary_shoot_ticks = 0
        elif not runtime.player_dead and shooting_active and moved <= cfg.idle_distance_epsilon:
            self._stationary_shoot_ticks += 1
            if self._stationary_shoot_ticks >= cfg.stationary_shoot_no_hit_grace_ticks:
                reward -= cfg.stationary_shoot_no_hit_cost
                breakdown["stationary_shoot_no_hit_cost"] -= cfg.stationary_shoot_no_hit_cost
        else:
            self._stationary_shoot_ticks = 0

        if not runtime.player_dead and (runtime.player_shoot_hold_active or delta_shots > 0) and not enemy_visible:
            self._shoot_no_target_ticks += 1
            if self._shoot_no_target_ticks >= cfg.shoot_no_target_grace_ticks:
                reward -= cfg.shoot_no_target_cost
                breakdown["shoot_no_target_cost"] -= cfg.shoot_no_target_cost
        else:
            self._shoot_no_target_ticks = 0

        if not runtime.player_dead:
            player_tile_x = int(runtime.player_world_x) // TILE_SIZE
            player_tile_y = int(runtime.player_world_y) // TILE_SIZE
            current_tile = (player_tile_x, player_tile_y)

            if current_tile not in self._visited_tiles:
                self._visited_tiles.add(current_tile)
                reward += cfg.tile_discovery_reward
                breakdown["tile_discovery_reward"] += cfg.tile_discovery_reward

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_shots_fired = runtime.player_shots_fired_total
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y

        return RewardStep(value=reward, stationary_ticks=self._idle_ticks, breakdown=breakdown)

    def _player_strafing(self, observation: dict[str, Any] | None) -> bool:
        if observation is None:
            return False
        state = observation.get("state")
        if state is None:
            return False
        state_arr = np.asarray(state, dtype=np.float32)
        if state_arr.size < 11:
            return False
        return bool(state_arr[10] >= 1.0)

    def _enemy_visible(self, observation: dict[str, Any] | None) -> bool:
        if not observation:
            return False
        rays = observation.get("rays")
        if rays is None:
            return False

        matrix = np.asarray(rays, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] < 2:
            return False
        if matrix.shape[0] == 0:
            return False

        return bool(np.min(matrix[:, 1]) < 1.0)
