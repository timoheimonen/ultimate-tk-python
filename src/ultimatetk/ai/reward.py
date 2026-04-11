from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ultimatetk.core.state import RuntimeState


@dataclass(frozen=True, slots=True)
class RewardConfig:
    step_cost: float = 0.0008
    kill_reward: float = 4.0
    hit_reward: float = 0.35
    look_at_enemy_reward: float = 0.0015
    strafing_reward: float = 0.0008
    crate_reward: float = 0.12
    damage_cost: float = 0.03
    death_cost: float = 8.0
    level_complete_reward: float = 18.0
    run_complete_reward: float = 30.0
    strafing_threat_tti_threshold: float = 0.35
    idle_ticks_threshold: int = 45
    idle_cost: float = 0.03
    idle_distance_epsilon: float = 3.0
    stationary_shoot_no_hit_cost: float = 0.04
    stationary_shoot_no_hit_grace_ticks: int = 10
    stuck_ticks_threshold: int = 150
    stuck_radius_epsilon: float = 24.0
    stuck_cost: float = 0.08


@dataclass(frozen=True, slots=True)
class RewardStep:
    value: float
    stationary_ticks: int


class RewardTracker:
    def __init__(self, config: RewardConfig | None = None) -> None:
        self._config = config or RewardConfig()
        self.reset(None)

    def reset(self, runtime: RuntimeState | None) -> None:
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
            self._stationary_shoot_no_hit_ticks = 0
            self._stuck_ticks = 0
            self._stuck_anchor_x = 0
            self._stuck_anchor_y = 0
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
        self._stationary_shoot_no_hit_ticks = 0
        self._stuck_ticks = 0
        self._stuck_anchor_x = runtime.player_world_x
        self._stuck_anchor_y = runtime.player_world_y

    def step(self, runtime: RuntimeState, observation: dict[str, Any] | None = None) -> RewardStep:
        cfg = self._config
        reward = -cfg.step_cost

        delta_kills = max(0, runtime.enemies_killed_by_player - self._prev_kills)
        delta_hits = max(0, runtime.player_hits_total - self._prev_hits)
        delta_crates = max(0, runtime.crates_collected_by_player - self._prev_crates)
        delta_shots = max(0, runtime.player_shots_fired_total - self._prev_shots_fired)
        delta_damage = max(0.0, runtime.player_damage_taken_total - self._prev_damage_taken)
        shooting_active = runtime.player_shoot_hold_active or delta_shots > 0

        reward += cfg.kill_reward * float(delta_kills)
        reward += cfg.hit_reward * float(delta_hits)
        reward += cfg.crate_reward * float(delta_crates)
        reward -= cfg.damage_cost * float(delta_damage)
        enemy_visible = _enemy_visible(observation)
        if enemy_visible:
            reward += cfg.look_at_enemy_reward
        if (
            enemy_visible
            and _player_strafing(observation)
            and (
                shooting_active
                or delta_hits > 0
                or _projectile_threat_close(observation, cfg.strafing_threat_tti_threshold)
            )
        ):
            reward += cfg.strafing_reward

        progression_changed = runtime.progression_event != self._prev_progression_event
        if progression_changed and runtime.progression_event == "level_complete":
            reward += cfg.level_complete_reward
        if progression_changed and runtime.progression_event == "run_complete":
            reward += cfg.run_complete_reward

        if runtime.player_dead and not self._prev_dead:
            reward -= cfg.death_cost

        moved = abs(runtime.player_world_x - self._prev_x) + abs(runtime.player_world_y - self._prev_y)

        if (
            not runtime.player_dead
            and moved <= cfg.idle_distance_epsilon
            and shooting_active
            and delta_hits == 0
        ):
            self._stationary_shoot_no_hit_ticks += 1
            if self._stationary_shoot_no_hit_ticks >= cfg.stationary_shoot_no_hit_grace_ticks:
                reward -= cfg.stationary_shoot_no_hit_cost
        else:
            self._stationary_shoot_no_hit_ticks = 0

        if runtime.player_dead or runtime.player_shoot_hold_active:
            self._stationary_ticks = 0
        elif moved <= cfg.idle_distance_epsilon:
            self._stationary_ticks += 1
            if self._stationary_ticks >= cfg.idle_ticks_threshold:
                reward -= cfg.idle_cost
        else:
            self._stationary_ticks = 0

        meaningful_progress = (
            delta_kills > 0
            or delta_hits > 0
            or delta_crates > 0
            or progression_changed
        )
        if runtime.player_dead:
            self._stuck_ticks = 0
            self._stuck_anchor_x = runtime.player_world_x
            self._stuck_anchor_y = runtime.player_world_y
        else:
            stuck_distance = abs(runtime.player_world_x - self._stuck_anchor_x) + abs(
                runtime.player_world_y - self._stuck_anchor_y
            )
            if stuck_distance <= cfg.stuck_radius_epsilon and not meaningful_progress:
                self._stuck_ticks += 1
                if self._stuck_ticks >= cfg.stuck_ticks_threshold:
                    reward -= cfg.stuck_cost
            else:
                self._stuck_ticks = 0
                self._stuck_anchor_x = runtime.player_world_x
                self._stuck_anchor_y = runtime.player_world_y

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_shots_fired = runtime.player_shots_fired_total
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y

        return RewardStep(value=reward, stationary_ticks=self._stationary_ticks)


def _enemy_visible(observation: dict[str, Any] | None) -> bool:
    if not observation:
        return False
    rays = observation.get("rays")
    if rays is None:
        return False

    matrix = np.asarray(rays, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return False

    return bool(np.min(matrix[:, 1]) < 1.0)


def _player_strafing(observation: dict[str, Any] | None) -> bool:
    if not observation:
        return False

    state = observation.get("state")
    if state is None:
        return False

    vector = np.asarray(state, dtype=np.float32)
    if vector.ndim != 1 or vector.shape[0] <= 10:
        return False

    return bool(vector[10] > 0.5)


def _projectile_threat_close(observation: dict[str, Any] | None, threshold: float) -> bool:
    if not observation:
        return False

    state = observation.get("state")
    if state is None:
        return False

    vector = np.asarray(state, dtype=np.float32)
    if vector.ndim != 1 or vector.shape[0] <= 13:
        return False

    return bool(vector[13] <= max(0.0, min(1.0, float(threshold))))
