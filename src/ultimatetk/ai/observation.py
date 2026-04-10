from __future__ import annotations

import math
from typing import Any

import numpy as np

from ultimatetk.core.state import RuntimeState
from ultimatetk.formats.lev import LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, TILE_SIZE
from ultimatetk.systems.gameplay_scene import GameplayStateView
from ultimatetk.systems.player_control import PLAYER_WEAPON_SLOTS, player_health_capacity, weapon_profile_for_slot


RAY_SECTOR_COUNT = 32
RAY_CHANNEL_COUNT = 8

CHANNEL_WALL = 0
CHANNEL_ENEMY = 1
CHANNEL_PROJECTILE = 2
CHANNEL_CRATE_WEAPON = 3
CHANNEL_CRATE_AMMO = 4
CHANNEL_CRATE_ENERGY = 5
CHANNEL_MINE = 6
CHANNEL_C4 = 7

STATE_FEATURE_COUNT = 16

_RAY_TRACE_STEP = 2
_PROJECTILE_TTI_CAP = 120.0
_CASH_CAP = 20000.0
_SHIELD_CAP = 30.0


def build_observation_space() -> Any:
    try:
        from gymnasium import spaces
    except ModuleNotFoundError as exc:
        raise RuntimeError("gymnasium is required for observation space creation") from exc

    return spaces.Dict(
        {
            "rays": spaces.Box(
                low=0.0,
                high=1.0,
                shape=(RAY_SECTOR_COUNT, RAY_CHANNEL_COUNT),
                dtype=np.float32,
            ),
            "state": spaces.Box(
                low=0.0,
                high=1.0,
                shape=(STATE_FEATURE_COUNT,),
                dtype=np.float32,
            ),
        },
    )


def blank_observation(runtime: RuntimeState) -> dict[str, np.ndarray]:
    rays = np.ones((RAY_SECTOR_COUNT, RAY_CHANNEL_COUNT), dtype=np.float32)
    state = np.zeros((STATE_FEATURE_COUNT,), dtype=np.float32)
    state[8] = 1.0 if runtime.shop_active else 0.0
    state[15] = 1.0 if runtime.player_target_system_enabled else 0.0
    return {
        "rays": rays,
        "state": state,
    }


def extract_observation(view: GameplayStateView | None, runtime: RuntimeState) -> dict[str, np.ndarray]:
    if view is None:
        return blank_observation(runtime)

    player = view.player
    player_x = float(player.center_x)
    player_y = float(player.center_y)
    player_angle = int(player.angle % 360)
    max_distance = _level_max_distance(view.level)

    rays = np.ones((RAY_SECTOR_COUNT, RAY_CHANNEL_COUNT), dtype=np.float32)
    wall_distances = _wall_distances_for_sectors(
        level=view.level,
        origin_x=player_x,
        origin_y=player_y,
        player_angle=player_angle,
        max_distance=max_distance,
    )
    rays[:, CHANNEL_WALL] = np.asarray(wall_distances, dtype=np.float32) / max_distance

    closest_projectile_distance = max_distance
    closest_projectile_tti = _PROJECTILE_TTI_CAP

    for enemy in view.enemies:
        if not enemy.alive:
            continue
        _accumulate_sector_distance(
            rays=rays,
            channel=CHANNEL_ENEMY,
            source_x=player_x,
            source_y=player_y,
            source_angle=player_angle,
            target_x=float(enemy.center_x),
            target_y=float(enemy.center_y),
            wall_distances=wall_distances,
            max_distance=max_distance,
        )

    for projectile in view.enemy_projectiles:
        distance = _accumulate_sector_distance(
            rays=rays,
            channel=CHANNEL_PROJECTILE,
            source_x=player_x,
            source_y=player_y,
            source_angle=player_angle,
            target_x=float(projectile.x),
            target_y=float(projectile.y),
            wall_distances=wall_distances,
            max_distance=max_distance,
        )
        if distance is not None and distance < closest_projectile_distance:
            closest_projectile_distance = distance
            projectile_speed = max(0.1, float(projectile.speed))
            closest_projectile_tti = min(_PROJECTILE_TTI_CAP, distance / projectile_speed)

    for crate in view.crates:
        if not crate.alive:
            continue
        if crate.type1 == 0:
            channel = CHANNEL_CRATE_WEAPON
        elif crate.type1 == 1:
            channel = CHANNEL_CRATE_AMMO
        elif crate.type1 == 2:
            channel = CHANNEL_CRATE_ENERGY
        else:
            continue
        _accumulate_sector_distance(
            rays=rays,
            channel=channel,
            source_x=player_x,
            source_y=player_y,
            source_angle=player_angle,
            target_x=float(crate.center_x),
            target_y=float(crate.center_y),
            wall_distances=wall_distances,
            max_distance=max_distance,
        )

    for explosive in view.player_explosives:
        if explosive.kind == "mine":
            channel = CHANNEL_MINE
        elif explosive.kind == "c4":
            channel = CHANNEL_C4
        else:
            continue

        _accumulate_sector_distance(
            rays=rays,
            channel=channel,
            source_x=player_x,
            source_y=player_y,
            source_angle=player_angle,
            target_x=float(explosive.x),
            target_y=float(explosive.y),
            wall_distances=wall_distances,
            max_distance=max_distance,
        )

    state = np.zeros((STATE_FEATURE_COUNT,), dtype=np.float32)
    health_capacity = max(1.0, float(player_health_capacity(player)))
    state[0] = _unit(float(player.health) / health_capacity)
    state[1] = _unit(float(player.shield) / _SHIELD_CAP)
    state[2] = _unit(float(player.cash) / _CASH_CAP)
    state[3] = _unit(float(player.current_weapon) / max(1.0, float(PLAYER_WEAPON_SLOTS - 1)))

    ammo_capacity = max(1.0, float(runtime.player_current_ammo_capacity))
    state[4] = _unit(float(runtime.player_current_ammo_units) / ammo_capacity)
    loading_time = max(1, weapon_profile_for_slot(player.current_weapon).loading_time)
    state[5] = _unit(float(player.load_count) / float(loading_time))
    state[6] = _unit(float(runtime.enemies_alive) / max(1.0, float(runtime.enemies_total)))
    state[7] = _unit(float(runtime.crates_alive) / max(1.0, float(runtime.crates_total)))
    state[8] = 1.0 if view.shop_active else 0.0
    state[9] = 1.0 if player.moving_forward else 0.0
    state[10] = 1.0 if player.moving_backward else 0.0
    state[11] = 1.0 if player.strafing else 0.0
    state[12] = 1.0 if player.turning else 0.0
    state[13] = _unit(closest_projectile_distance / max_distance)
    state[14] = _unit(closest_projectile_tti / _PROJECTILE_TTI_CAP)
    state[15] = 1.0 if player.target_system_enabled else 0.0

    return {
        "rays": rays,
        "state": state,
    }


def _wall_distances_for_sectors(
    *,
    level: LevelData,
    origin_x: float,
    origin_y: float,
    player_angle: int,
    max_distance: float,
) -> list[float]:
    sector_angle = 360.0 / float(RAY_SECTOR_COUNT)
    result: list[float] = [max_distance for _ in range(RAY_SECTOR_COUNT)]

    for sector in range(RAY_SECTOR_COUNT):
        sample_angle = (player_angle + (sector * sector_angle) + (sector_angle * 0.5)) % 360.0
        radians = math.radians(sample_angle)
        sin_angle = math.sin(radians)
        cos_angle = math.cos(radians)

        distance = 0.0
        while distance < max_distance:
            distance += _RAY_TRACE_STEP
            x = int(origin_x + (sin_angle * distance))
            y = int(origin_y + (cos_angle * distance))
            if not _is_floor_pixel(level, x=x, y=y):
                result[sector] = min(distance, max_distance)
                break

    return result


def _accumulate_sector_distance(
    *,
    rays: np.ndarray,
    channel: int,
    source_x: float,
    source_y: float,
    source_angle: int,
    target_x: float,
    target_y: float,
    wall_distances: list[float],
    max_distance: float,
) -> float | None:
    dx = target_x - source_x
    dy = target_y - source_y
    distance = math.hypot(dx, dy)
    if distance <= 0.0 or distance > max_distance:
        return None

    angle = math.degrees(math.atan2(dx, dy)) % 360.0
    relative = (angle - float(source_angle)) % 360.0
    sector_angle = 360.0 / float(RAY_SECTOR_COUNT)
    sector = int(relative // sector_angle)
    sector = max(0, min(RAY_SECTOR_COUNT - 1, sector))

    if distance > wall_distances[sector]:
        return None

    normalized = _unit(distance / max_distance)
    if normalized < float(rays[sector, channel]):
        rays[sector, channel] = normalized
    return distance


def _level_max_distance(level: LevelData) -> float:
    width = float(level.level_x_size * TILE_SIZE)
    height = float(level.level_y_size * TILE_SIZE)
    return max(1.0, math.hypot(width, height))


def _is_floor_pixel(level: LevelData, *, x: int, y: int) -> bool:
    if x < 0 or y < 0:
        return False

    tile_x = x // TILE_SIZE
    tile_y = y // TILE_SIZE
    if tile_x < 0 or tile_y < 0:
        return False
    if tile_x >= level.level_x_size or tile_y >= level.level_y_size:
        return False

    block = level.blocks[tile_y * level.level_x_size + tile_x]
    return block.type == FLOOR_BLOCK_TYPE


def _unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value
