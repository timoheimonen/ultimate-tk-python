from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from ultimatetk.formats.lev import DIFF_ENEMIES, LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, TILE_SIZE
from ultimatetk.systems.player_control import (
    PLAYER_COLLISION_SIZE,
    SHOT_TRACE_STEP,
    PlayerState,
    ShotEvent,
    apply_player_damage,
    weapon_profile_for_slot,
)


ENEMY_SIZE = 28
ENEMY_COLLISION_INSET = 5
ENEMY_FLASH_TICKS = 3
MAX_SPAWNED_ENEMIES = 24
ENEMY_ROTATION_STEP_DEGREES = 9
ENEMY_ALIGNMENT_TOLERANCE_DEGREES = 9

ENEMY_WEAPON_SLOT: tuple[int, ...] = (1, 2, 3, 4, 5, 0, 8, 10)
ENEMY_SPEED: tuple[float, ...] = (2.0, 2.0, 2.0, 3.0, 2.0, 2.0, 1.0, 2.0)


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
    0.4,
    16.0,
)

WEAPON_RANGE: tuple[int, ...] = (
    34,
    108,
    126,
    108,
    160,
    160,
    120,
    80,
    100,
    34,
    100,
    34,
)

WEAPON_PELLET_COUNT: tuple[int, ...] = (
    1,
    1,
    6,
    1,
    1,
    1,
    1,
    1,
    6,
    1,
    1,
    1,
)

WEAPON_ANGLE_SPREAD: tuple[int, ...] = (
    1,
    1,
    20,
    1,
    1,
    1,
    1,
    1,
    20,
    1,
    1,
    1,
)

WEAPON_EXPLOSIVE_SPLASH_RADIUS: tuple[int, ...] = (
    0,
    0,
    0,
    0,
    0,
    48,
    56,
    64,
    0,
    40,
    0,
    40,
)


@dataclass(slots=True)
class EnemyState:
    enemy_id: int
    type_index: int
    x: float
    y: float
    health: float
    max_health: float
    angle: int = 0
    target_angle: int = 0
    walk_ticks: int = 0
    load_count: int = 0
    shoot_count: int = 0
    sees_player: bool = False
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


@dataclass(frozen=True, slots=True)
class EnemyShotResolution:
    player_hit: bool
    impact_x: int
    impact_y: int
    damage: float


@dataclass(frozen=True, slots=True)
class EnemyBehaviorReport:
    shots_fired: int = 0
    hits_on_player: int = 0
    damage_to_player: float = 0.0


@dataclass(frozen=True, slots=True)
class EnemyAttackResult:
    hit_count: int = 0
    total_damage: float = 0.0


def enemy_health_for_type(type_index: int) -> float:
    if 0 <= type_index < len(ENEMY_HEALTH):
        return ENEMY_HEALTH[type_index]
    return ENEMY_HEALTH[0]


def weapon_damage_for_slot(weapon_slot: int) -> float:
    if 0 <= weapon_slot < len(WEAPON_DAMAGE):
        return WEAPON_DAMAGE[weapon_slot]
    return WEAPON_DAMAGE[0]


def weapon_range_for_slot(weapon_slot: int) -> int:
    if 0 <= weapon_slot < len(WEAPON_RANGE):
        return WEAPON_RANGE[weapon_slot]
    return WEAPON_RANGE[0]


def weapon_pellet_count_for_slot(weapon_slot: int) -> int:
    if 0 <= weapon_slot < len(WEAPON_PELLET_COUNT):
        return WEAPON_PELLET_COUNT[weapon_slot]
    return WEAPON_PELLET_COUNT[0]


def weapon_angle_spread_for_slot(weapon_slot: int) -> int:
    if 0 <= weapon_slot < len(WEAPON_ANGLE_SPREAD):
        return WEAPON_ANGLE_SPREAD[weapon_slot]
    return WEAPON_ANGLE_SPREAD[0]


def weapon_explosive_splash_radius_for_slot(weapon_slot: int) -> int:
    if 0 <= weapon_slot < len(WEAPON_EXPLOSIVE_SPLASH_RADIUS):
        return WEAPON_EXPLOSIVE_SPLASH_RADIUS[weapon_slot]
    return WEAPON_EXPLOSIVE_SPLASH_RADIUS[0]


def enemy_weapon_for_type(type_index: int) -> int:
    if 0 <= type_index < len(ENEMY_WEAPON_SLOT):
        return ENEMY_WEAPON_SLOT[type_index]
    return ENEMY_WEAPON_SLOT[0]


def enemy_speed_for_type(type_index: int) -> float:
    if 0 <= type_index < len(ENEMY_SPEED):
        return ENEMY_SPEED[type_index]
    return ENEMY_SPEED[0]


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
        spawn_angle = _spawn_angle_for_tile(preferred[0], preferred[1], enemy_id=0)
        enemies.append(
            EnemyState(
                enemy_id=0,
                type_index=first_type,
                x=float(preferred[0] * TILE_SIZE),
                y=float(preferred[1] * TILE_SIZE),
                health=health,
                max_health=health,
                angle=spawn_angle,
                target_angle=spawn_angle,
            ),
        )

    for enemy_id, type_index in enumerate(remaining_types, start=len(enemies)):
        tile = _pick_spawn_tile(candidates, used, index=index, stride=stride, existing=enemies)
        if tile is None:
            break

        used.add(tile)
        index = (index + stride) % len(candidates)
        health = enemy_health_for_type(type_index)
        spawn_angle = _spawn_angle_for_tile(tile[0], tile[1], enemy_id=enemy_id)
        enemies.append(
            EnemyState(
                enemy_id=enemy_id,
                type_index=type_index,
                x=float(tile[0] * TILE_SIZE),
                y=float(tile[1] * TILE_SIZE),
                health=health,
                max_health=health,
                angle=spawn_angle,
                target_angle=spawn_angle,
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


def update_enemy_behavior(
    level: LevelData,
    enemies: Sequence[EnemyState],
    player: PlayerState,
) -> EnemyBehaviorReport:
    shots_fired = 0
    hits_on_player = 0
    damage_to_player = 0.0

    for enemy in enemies:
        if not enemy.alive:
            enemy.sees_player = False
            continue

        if player.dead:
            enemy.sees_player = False
            _advance_enemy_patrol(
                enemy,
                level,
                enemies=enemies,
                player=player,
            )
            _advance_enemy_reload(enemy, weapon_slot=enemy_weapon_for_type(enemy.type_index))
            continue

        weapon_slot = enemy_weapon_for_type(enemy.type_index)
        player_angle = _angle_to_point(enemy.center_x, enemy.center_y, player.center_x, player.center_y)
        enemy.target_angle = player_angle
        enemy.angle = _rotate_towards_angle(enemy.angle, player_angle, step=ENEMY_ROTATION_STEP_DEGREES)

        enemy.sees_player = _line_of_sight_clear(
            level,
            start_x=enemy.center_x,
            start_y=enemy.center_y,
            end_x=player.center_x,
            end_y=player.center_y,
        )

        distance_to_player = math.hypot(player.center_x - enemy.center_x, player.center_y - enemy.center_y)
        if enemy.sees_player:
            enemy.walk_ticks = 0

            attack_range = weapon_range_for_slot(weapon_slot)
            follow_distance = max(40.0, attack_range * 0.55)
            if distance_to_player > follow_distance:
                _move_enemy_with_collision(
                    enemy,
                    level,
                    angle=enemy.angle,
                    speed=enemy_speed_for_type(enemy.type_index),
                    enemies=enemies,
                    player=player,
                )

            if _can_enemy_fire(enemy, weapon_slot=weapon_slot, distance_to_player=distance_to_player):
                shots_fired += 1
                enemy.load_count = 0
                enemy.shoot_count += 1
                attack = resolve_enemy_attack_against_player(
                    level,
                    enemy=enemy,
                    player=player,
                    weapon_slot=weapon_slot,
                )
                hits_on_player += attack.hit_count
                damage_to_player += attack.total_damage
        else:
            _advance_enemy_patrol(
                enemy,
                level,
                enemies=enemies,
                player=player,
            )

        _advance_enemy_reload(enemy, weapon_slot=weapon_slot)

    return EnemyBehaviorReport(
        shots_fired=shots_fired,
        hits_on_player=hits_on_player,
        damage_to_player=damage_to_player,
    )


def resolve_enemy_shot_against_player(
    level: LevelData,
    *,
    enemy: EnemyState,
    player: PlayerState,
    weapon_slot: int,
    angle: int | None = None,
    damage: float | None = None,
    max_distance: int | None = None,
) -> EnemyShotResolution:
    angle_radians = math.radians((enemy.angle if angle is None else angle) % 360)
    ray_damage = weapon_damage_for_slot(weapon_slot) if damage is None else max(0.0, damage)
    trace_distance = weapon_range_for_slot(weapon_slot) if max_distance is None else max(0, max_distance)

    origin_x = enemy.center_x + (10.0 * math.sin(angle_radians))
    origin_y = enemy.center_y + (10.0 * math.cos(angle_radians))

    px = int(origin_x)
    py = int(origin_y)
    for distance in range(0, trace_distance + 1, max(1, SHOT_TRACE_STEP)):
        x = int(origin_x + (distance * math.sin(angle_radians)))
        y = int(origin_y + (distance * math.cos(angle_radians)))

        if not _is_floor_pixel(level, x, y):
            return EnemyShotResolution(player_hit=False, impact_x=px, impact_y=py, damage=0.0)

        if _player_at_point(player, x=x, y=y):
            return EnemyShotResolution(
                player_hit=True,
                impact_x=int(player.center_x),
                impact_y=int(player.center_y),
                damage=ray_damage,
            )

        px = x
        py = y

    return EnemyShotResolution(player_hit=False, impact_x=px, impact_y=py, damage=0.0)


def resolve_enemy_attack_against_player(
    level: LevelData,
    *,
    enemy: EnemyState,
    player: PlayerState,
    weapon_slot: int,
) -> EnemyAttackResult:
    pellet_count = max(1, weapon_pellet_count_for_slot(weapon_slot))
    spread = weapon_angle_spread_for_slot(weapon_slot)
    pellet_damage = weapon_damage_for_slot(weapon_slot) / pellet_count

    hit_count = 0
    total_damage = 0.0
    for pellet_index in range(pellet_count):
        shot_angle = _enemy_shot_angle(
            enemy,
            weapon_slot=weapon_slot,
            spread=spread,
            pellet_index=pellet_index,
        )
        shot = resolve_enemy_shot_against_player(
            level,
            enemy=enemy,
            player=player,
            weapon_slot=weapon_slot,
            angle=shot_angle,
            damage=pellet_damage,
        )
        dealt_damage = 0.0
        if shot.player_hit:
            dealt_damage = shot.damage
        else:
            splash_radius = weapon_explosive_splash_radius_for_slot(weapon_slot)
            if splash_radius > 0:
                dealt_damage = _explosive_splash_damage(
                    player,
                    impact_x=shot.impact_x,
                    impact_y=shot.impact_y,
                    max_damage=pellet_damage,
                    radius=splash_radius,
                )

        if dealt_damage <= 0:
            continue

        hit_count += 1
        total_damage += dealt_damage
        apply_player_damage(player, dealt_damage)
        if player.dead:
            break

    return EnemyAttackResult(hit_count=hit_count, total_damage=total_damage)


def _can_enemy_fire(
    enemy: EnemyState,
    *,
    weapon_slot: int,
    distance_to_player: float,
) -> bool:
    profile = weapon_profile_for_slot(weapon_slot)
    if enemy.load_count < profile.loading_time:
        return False
    if _angular_distance(enemy.angle, enemy.target_angle) > ENEMY_ALIGNMENT_TOLERANCE_DEGREES:
        return False
    if distance_to_player > weapon_range_for_slot(weapon_slot):
        return False
    return True


def _advance_enemy_reload(enemy: EnemyState, *, weapon_slot: int) -> None:
    loading_time = weapon_profile_for_slot(weapon_slot).loading_time
    if enemy.load_count < loading_time:
        enemy.load_count += 1


def _advance_enemy_patrol(
    enemy: EnemyState,
    level: LevelData,
    *,
    enemies: Sequence[EnemyState],
    player: PlayerState,
) -> None:
    if enemy.walk_ticks <= 0:
        seed = enemy.enemy_id * 31 + int(enemy.x) * 3 + int(enemy.y) * 5
        enemy.walk_ticks = 16 + (seed % 26)
        turn = 90 if seed % 2 == 0 else -90
        enemy.target_angle = (enemy.angle + turn) % 360

    enemy.angle = _rotate_towards_angle(enemy.angle, enemy.target_angle, step=ENEMY_ROTATION_STEP_DEGREES)
    moved = _move_enemy_with_collision(
        enemy,
        level,
        angle=enemy.angle,
        speed=enemy_speed_for_type(enemy.type_index),
        enemies=enemies,
        player=player,
    )
    if moved:
        enemy.walk_ticks -= 1
    else:
        enemy.walk_ticks = 0


def _move_enemy_with_collision(
    enemy: EnemyState,
    level: LevelData,
    *,
    angle: int,
    speed: float,
    enemies: Sequence[EnemyState],
    player: PlayerState,
) -> bool:
    angle_radians = math.radians(angle % 360)
    new_x = enemy.x + (speed * math.sin(angle_radians))
    new_y = enemy.y + (speed * math.cos(angle_radians))

    moved = False
    if not _enemy_move_blocked(
        level,
        x=new_x,
        y=enemy.y,
        moving_enemy=enemy,
        enemies=enemies,
        player=player,
    ):
        enemy.x = new_x
        moved = True

    if not _enemy_move_blocked(
        level,
        x=enemy.x,
        y=new_y,
        moving_enemy=enemy,
        enemies=enemies,
        player=player,
    ):
        enemy.y = new_y
        moved = True

    return moved


def _enemy_move_blocked(
    level: LevelData,
    *,
    x: float,
    y: float,
    moving_enemy: EnemyState,
    enemies: Sequence[EnemyState],
    player: PlayerState,
) -> bool:
    left = int(x) + ENEMY_COLLISION_INSET
    right = int(x) + ENEMY_SIZE - ENEMY_COLLISION_INSET
    top = int(y) + ENEMY_COLLISION_INSET
    bottom = int(y) + ENEMY_SIZE - ENEMY_COLLISION_INSET

    if not _is_floor_pixel(level, left, top):
        return True
    if not _is_floor_pixel(level, right, top):
        return True
    if not _is_floor_pixel(level, left, bottom):
        return True
    if not _is_floor_pixel(level, right, bottom):
        return True

    if _rectangles_overlap(
        x,
        y,
        ENEMY_SIZE,
        ENEMY_SIZE,
        player.x,
        player.y,
        PLAYER_COLLISION_SIZE,
        PLAYER_COLLISION_SIZE,
        inset=ENEMY_COLLISION_INSET,
    ):
        return True

    for enemy in enemies:
        if enemy is moving_enemy or enemy.enemy_id == moving_enemy.enemy_id:
            continue
        if not enemy.alive:
            continue
        if _rectangles_overlap(
            x,
            y,
            ENEMY_SIZE,
            ENEMY_SIZE,
            enemy.x,
            enemy.y,
            ENEMY_SIZE,
            ENEMY_SIZE,
            inset=ENEMY_COLLISION_INSET,
        ):
            return True

    return False


def _rectangles_overlap(
    ax: float,
    ay: float,
    aw: int,
    ah: int,
    bx: float,
    by: float,
    bw: int,
    bh: int,
    *,
    inset: int,
) -> bool:
    a_left = ax + inset
    a_right = ax + aw - inset
    a_top = ay + inset
    a_bottom = ay + ah - inset

    b_left = bx + inset
    b_right = bx + bw - inset
    b_top = by + inset
    b_bottom = by + bh - inset

    return (
        a_left < b_right
        and a_right > b_left
        and a_top < b_bottom
        and a_bottom > b_top
    )


def _line_of_sight_clear(
    level: LevelData,
    *,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> bool:
    dx = end_x - start_x
    dy = end_y - start_y
    distance = int(math.hypot(dx, dy))
    if distance <= 0:
        return True

    for traveled in range(0, distance + 1, max(1, SHOT_TRACE_STEP)):
        ratio = traveled / distance
        x = int(start_x + (dx * ratio))
        y = int(start_y + (dy * ratio))
        if not _is_floor_pixel(level, x, y):
            return False
    return True


def _angle_to_point(origin_x: float, origin_y: float, target_x: float, target_y: float) -> int:
    dx = target_x - origin_x
    dy = target_y - origin_y
    angle = int(math.degrees(math.atan2(dx, dy)))
    return angle % 360


def _rotate_towards_angle(current: int, target: int, *, step: int) -> int:
    delta = ((target - current + 540) % 360) - 180
    if abs(delta) <= step:
        return target % 360
    if delta > 0:
        return (current + step) % 360
    return (current - step) % 360


def _angular_distance(first: int, second: int) -> int:
    return abs(((second - first + 540) % 360) - 180)


def _enemy_shot_angle(
    enemy: EnemyState,
    *,
    weapon_slot: int,
    spread: int,
    pellet_index: int,
) -> int:
    if spread <= 1:
        return enemy.angle

    seed = (
        enemy.enemy_id * 97
        + enemy.shoot_count * 53
        + weapon_slot * 17
        + pellet_index * 31
    )
    offset = (seed % spread) - (spread // 2)
    return (enemy.angle + offset) % 360


def _explosive_splash_damage(
    player: PlayerState,
    *,
    impact_x: int,
    impact_y: int,
    max_damage: float,
    radius: int,
) -> float:
    if radius <= 0 or max_damage <= 0:
        return 0.0

    distance = math.hypot(player.center_x - impact_x, player.center_y - impact_y)
    if distance >= radius:
        return 0.0

    falloff = 1.0 - (distance / radius)
    if falloff <= 0:
        return 0.0
    return max_damage * falloff


def _player_at_point(
    player: PlayerState,
    *,
    x: int,
    y: int,
) -> bool:
    if x <= player.x + ENEMY_COLLISION_INSET:
        return False
    if x >= player.x + PLAYER_COLLISION_SIZE - ENEMY_COLLISION_INSET:
        return False
    if y <= player.y + ENEMY_COLLISION_INSET:
        return False
    if y >= player.y + PLAYER_COLLISION_SIZE - ENEMY_COLLISION_INSET:
        return False
    return True


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


def _spawn_angle_for_tile(tile_x: int, tile_y: int, *, enemy_id: int) -> int:
    return (tile_x * 29 + tile_y * 17 + enemy_id * 47) % 360


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
