from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppMode(str, Enum):
    BOOT = "boot"
    MAIN_MENU = "main_menu"
    GAMEPLAY = "gameplay"
    LEVEL_COMPLETE = "level_complete"
    RUN_COMPLETE = "run_complete"
    GAME_OVER = "game_over"
    SHUTDOWN = "shutdown"


@dataclass(slots=True)
class RuntimeState:
    mode: AppMode = AppMode.BOOT
    running: bool = True
    simulation_frame: int = 0
    render_frame: int = 0
    elapsed_seconds: float = 0.0
    last_render_digest: int = 0
    last_render_width: int = 0
    last_render_height: int = 0
    player_world_x: int = 0
    player_world_y: int = 0
    player_angle_degrees: int = 0
    player_weapon_slot: int = 0
    player_current_ammo_type_index: int = -1
    player_current_ammo_units: int = 0
    player_current_ammo_capacity: int = 0
    player_ammo_pools: tuple[int, ...] = ()
    player_ammo_capacities: tuple[int, ...] = ()
    player_load_count: int = 0
    player_fire_ticks: int = 0
    player_shots_fired_total: int = 0
    player_cash: int = 0
    player_shield: int = 0
    player_target_system_enabled: bool = False
    shop_active: bool = False
    shop_selection_row: int = 0
    shop_selection_column: int = 0
    shop_last_action: str = ""
    shop_last_category: str = ""
    shop_last_success: bool = False
    shop_last_units: int = 0
    shop_last_cash_delta: int = 0
    shop_last_reason: str = ""
    player_health: int = 0
    player_dead: bool = False
    player_hits_total: int = 0
    player_hits_taken_total: int = 0
    player_damage_taken_total: float = 0.0
    enemies_total: int = 0
    enemies_alive: int = 0
    enemies_killed_by_player: int = 0
    crates_total: int = 0
    crates_alive: int = 0
    crates_destroyed_by_player: int = 0
    crates_collected_by_player: int = 0
    enemy_shots_fired_total: int = 0
    enemy_hits_total: int = 0
    enemy_damage_to_player_total: float = 0.0
    enemy_projectiles_active: int = 0
    player_explosives_active: int = 0
    player_mines_active: int = 0
    player_mines_armed: int = 0
    player_c4_active: int = 0
    player_c4_hot: int = 0
    player_explosive_detonations_total: int = 0
    game_over_active: bool = False
    game_over_ticks_remaining: int = 0
    progression_event: str = ""
    progression_from_level_index: int = -1
    progression_to_level_index: int = -1
    progression_has_next_level: bool = False
    progression_ticks_remaining: int = 0


@dataclass(slots=True)
class SessionState:
    episode_index: int = 0
    level_index: int = 0
    player_name: str = "Player1"
