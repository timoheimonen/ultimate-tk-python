from __future__ import annotations

from dataclasses import dataclass

from ultimatetk.core.state import RuntimeState


@dataclass(frozen=True, slots=True)
class RewardConfig:
    step_penalty: float = -0.001
    kill_reward: float = 2.0
    hit_reward: float = 0.15
    crate_reward: float = 0.10
    damage_penalty: float = 0.02
    death_penalty: float = 15.0
    level_complete_reward: float = 5.0
    run_complete_reward: float = 25.0
    idle_ticks_threshold: int = 60
    idle_penalty: float = 0.02
    idle_distance_epsilon: float = 1.5


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
            self._prev_x = 0
            self._prev_y = 0
            self._stationary_ticks = 0
            return

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y
        self._stationary_ticks = 0

    def step(self, runtime: RuntimeState) -> RewardStep:
        cfg = self._config
        reward = cfg.step_penalty

        delta_kills = max(0, runtime.enemies_killed_by_player - self._prev_kills)
        delta_hits = max(0, runtime.player_hits_total - self._prev_hits)
        delta_crates = max(0, runtime.crates_collected_by_player - self._prev_crates)
        delta_damage = max(0.0, runtime.player_damage_taken_total - self._prev_damage_taken)

        reward += cfg.kill_reward * float(delta_kills)
        reward += cfg.hit_reward * float(delta_hits)
        reward += cfg.crate_reward * float(delta_crates)
        reward -= cfg.damage_penalty * float(delta_damage)

        progression_changed = runtime.progression_event != self._prev_progression_event
        if progression_changed and runtime.progression_event == "level_complete":
            reward += cfg.level_complete_reward
        if progression_changed and runtime.progression_event == "run_complete":
            reward += cfg.run_complete_reward

        if runtime.player_dead and not self._prev_dead:
            reward -= cfg.death_penalty

        moved = abs(runtime.player_world_x - self._prev_x) + abs(runtime.player_world_y - self._prev_y)
        if runtime.player_dead or runtime.shop_active:
            self._stationary_ticks = 0
        elif moved <= cfg.idle_distance_epsilon:
            self._stationary_ticks += 1
            if self._stationary_ticks >= cfg.idle_ticks_threshold:
                reward -= cfg.idle_penalty
        else:
            self._stationary_ticks = 0

        self._prev_kills = runtime.enemies_killed_by_player
        self._prev_hits = runtime.player_hits_total
        self._prev_crates = runtime.crates_collected_by_player
        self._prev_damage_taken = runtime.player_damage_taken_total
        self._prev_dead = runtime.player_dead
        self._prev_progression_event = runtime.progression_event
        self._prev_x = runtime.player_world_x
        self._prev_y = runtime.player_world_y

        return RewardStep(value=reward, stationary_ticks=self._stationary_ticks)
