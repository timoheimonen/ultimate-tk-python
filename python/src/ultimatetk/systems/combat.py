from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from ultimatetk.formats.lev import DIFF_ENEMIES, LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, TILE_SIZE
from ultimatetk.systems.player_control import SHOT_TRACE_STEP, ShotEvent


ENEMY_SIZE = 28
ENEMY_COLLISION_INSET = 5
ENEMY_FLASH_TICKS = 3
MAX_SPAWNED_ENEMIES = 24


ENEMY_HEALTH: tuple[float, ...] = (18.0, 28.0, 40.0, 50.0, 40.0, 10.0, 150.0, 100.0)

WEAPON_DAMAGE: tuple[float, ...] = (
    3.0,
    5.0,
    18.0,
    5.0,
    6.0,
    20.0,
    14.0,
    28.0,
    18.0,
    10.0,
    4.0,
    16.0,
)


@dataclass(slots=True)
class EnemyState:
    enemy_id: int
    type_index: int
    x: float
    y: float
    health: float
    max_health: float
    alive: bool = True
    hit_flash_ticks: int = 0

    @property
    def center_x(self) -> float:
        return self.x + (ENEMY_SIZE // 2)

    @property
    def center_y(self) -> float:
        return self.y + (ENEMY_SIZE // 2)

    def apply_damage(self, damage: float) -> bool:
        if not self.alive:
            return False
        self.health -= damage
        if self.health <= 0:
            self.health = 0.0
            self.alive = False
            return True
        return False


@dataclass(frozen=True, slots=True)
class ShotResolution:
    enemy_id: int | None
    impact_x: int
    impact_y: int
    damage: float
    enemy_killed: bool = False


def enemy_health_for_type(type_index: int) -> float:
    if 0 <= type_index < len(ENEMY_HEALTH):
        return ENEMY_HEALTH[type_index]
    return ENEMY_HEALTH[0]


def weapon_damage_for_slot(weapon_slot: int) -> float:
    if 0 <= weapon_slot < len(WEAPON_DAMAGE):
        return WEAPON_DAMAGE[weapon_slot]
    return WEAPON_DAMAGE[0]


def spawn_enemies_for_level(
    level: LevelData,
    *,
    player_x: float,
    player_y: float,
    max_enemies: int = MAX_SPAWNED_ENEMIES,
) -> tuple[EnemyState, ...]:
    requested_types = _expand_enemy_type_counts(level, max_enemies=max_enemies)
    if not requested_types:
        return ()

    start_tile_x = int(player_x) // TILE_SIZE
    start_tile_y = int(player_y) // TILE_SIZE

    candidates = _collect_floor_spawn_tiles(level, start_tile_x=start_tile_x, start_tile_y=start_tile_y)
    if not candidates:
        return ()

    preferred = _preferred_spawn_tile_in_front(level, start_tile_x=start_tile_x, start_tile_y=start_tile_y)

    stride = max(1, (len(candidates) // max(1, len(requested_types))) + 1)
    index = (start_tile_x * 31 + start_tile_y * 17) % len(candidates)

    used: set[tuple[int, int]] = set()
    enemies: list[EnemyState] = []

    remaining_types = list(requested_types)
    if preferred is not None and preferred in candidates and remaining_types:
        first_type = remaining_types.pop(0)
        used.add(preferred)
        health = enemy_health_for_type(first_type)
        enemies.append(
            EnemyState(
                enemy_id=0,
                type_index=first_type,
                x=float(preferred[0] * TILE_SIZE),
                y=float(preferred[1] * TILE_SIZE),
                health=health,
                max_health=health,
            ),
        )

    for enemy_id, type_index in enumerate(remaining_types, start=len(enemies)):
        tile = _pick_spawn_tile(candidates, used, index=index, stride=stride, existing=enemies)
        if tile is None:
            break

        used.add(tile)
        index = (index + stride) % len(candidates)
        health = enemy_health_for_type(type_index)
        enemies.append(
            EnemyState(
                enemy_id=enemy_id,
                type_index=type_index,
                x=float(tile[0] * TILE_SIZE),
                y=float(tile[1] * TILE_SIZE),
                health=health,
                max_health=health,
            ),
        )

    return tuple(enemies)


def resolve_shot_against_enemies(
    level: LevelData,
    enemies: Sequence[EnemyState],
    shot: ShotEvent,
) -> ShotResolution:
    angle_radians = math.radians(shot.angle % 360)
    damage = weapon_damage_for_slot(shot.weapon_slot)

    px = int(shot.origin_x)
    py = int(shot.origin_y)
    for distance in range(0, shot.max_distance + 1, max(1, SHOT_TRACE_STEP)):
        x = int(shot.origin_x + (distance * math.sin(angle_radians)))
        y = int(shot.origin_y + (distance * math.cos(angle_radians)))

        if not _is_floor_pixel(level, x, y):
            return ShotResolution(enemy_id=None, impact_x=px, impact_y=py, damage=0.0)

        enemy = _enemy_at_point(enemies, x=x, y=y)
        if enemy is not None:
            enemy.hit_flash_ticks = ENEMY_FLASH_TICKS
            killed = enemy.apply_damage(damage)
            return ShotResolution(
                enemy_id=enemy.enemy_id,
                impact_x=int(enemy.center_x),
                impact_y=int(enemy.center_y),
                damage=damage,
                enemy_killed=killed,
            )

        px = x
        py = y

    return ShotResolution(enemy_id=None, impact_x=px, impact_y=py, damage=0.0)


def advance_enemy_effects(enemies: Sequence[EnemyState]) -> None:
    for enemy in enemies:
        if enemy.hit_flash_ticks > 0:
            enemy.hit_flash_ticks -= 1


def alive_enemy_count(enemies: Sequence[EnemyState]) -> int:
    return sum(1 for enemy in enemies if enemy.alive)


def _expand_enemy_type_counts(level: LevelData, *, max_enemies: int) -> list[int]:
    requested: list[int] = []
    for type_index, count in enumerate(level.general_info.enemies[:DIFF_ENEMIES]):
        for _ in range(max(0, int(count))):
            requested.append(type_index)
            if len(requested) >= max_enemies:
                return requested
    return requested


def _collect_floor_spawn_tiles(
    level: LevelData,
    *,
    start_tile_x: int,
    start_tile_y: int,
) -> list[tuple[int, int]]:
    tiles: list[tuple[int, int]] = []
    for tile_y in range(level.level_y_size):
        for tile_x in range(level.level_x_size):
            if not _is_floor_tile(level, tile_x, tile_y):
                continue
            if abs(tile_x - start_tile_x) <= 1 and abs(tile_y - start_tile_y) <= 1:
                continue
            tiles.append((tile_x, tile_y))
    return tiles


def _preferred_spawn_tile_in_front(
    level: LevelData,
    *,
    start_tile_x: int,
    start_tile_y: int,
) -> tuple[int, int] | None:
    for distance in range(2, 7):
        tile_y = start_tile_y + distance
        for dx in (0, -1, 1, -2, 2):
            tile_x = start_tile_x + dx
            if _is_floor_tile(level, tile_x, tile_y):
                return tile_x, tile_y
    return None


def _pick_spawn_tile(
    candidates: Sequence[tuple[int, int]],
    used: set[tuple[int, int]],
    *,
    index: int,
    stride: int,
    existing: Sequence[EnemyState],
) -> tuple[int, int] | None:
    if not candidates:
        return None

    probe = index
    for _ in range(len(candidates)):
        tile = candidates[probe]
        probe = (probe + stride) % len(candidates)
        if tile in used:
            continue
        if _tile_too_close_to_existing(tile, existing):
            continue
        return tile
    return None


def _tile_too_close_to_existing(
    tile: tuple[int, int],
    existing: Sequence[EnemyState],
) -> bool:
    tx, ty = tile
    for enemy in existing:
        ex = int(enemy.x) // TILE_SIZE
        ey = int(enemy.y) // TILE_SIZE
        if abs(tx - ex) <= 1 and abs(ty - ey) <= 1:
            return True
    return False


def _enemy_at_point(
    enemies: Sequence[EnemyState],
    *,
    x: int,
    y: int,
) -> EnemyState | None:
    for enemy in enemies:
        if not enemy.alive:
            continue
        if x <= enemy.x + ENEMY_COLLISION_INSET:
            continue
        if x >= enemy.x + ENEMY_SIZE - ENEMY_COLLISION_INSET:
            continue
        if y <= enemy.y + ENEMY_COLLISION_INSET:
            continue
        if y >= enemy.y + ENEMY_SIZE - ENEMY_COLLISION_INSET:
            continue
        return enemy
    return None


def _is_floor_tile(level: LevelData, tile_x: int, tile_y: int) -> bool:
    if tile_x < 0 or tile_x >= level.level_x_size or tile_y < 0 or tile_y >= level.level_y_size:
        return False
    block = level.blocks[tile_y * level.level_x_size + tile_x]
    return block.type == FLOOR_BLOCK_TYPE


def _is_floor_pixel(level: LevelData, x: int, y: int) -> bool:
    if x < 0 or y < 0:
        return False
    tile_x = x // TILE_SIZE
    tile_y = y // TILE_SIZE
    return _is_floor_tile(level, tile_x, tile_y)
