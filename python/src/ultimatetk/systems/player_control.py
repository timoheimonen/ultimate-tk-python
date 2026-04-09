from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from ultimatetk.core.events import InputAction
from ultimatetk.formats.lev import DIFF_BULLETS, LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE


PLAYER_ROTATION_STEP_DEGREES = 9
PLAYER_BASE_SPEED = 2.0
PLAYER_COLLISION_SIZE = 28
PLAYER_CENTER_OFFSET = PLAYER_COLLISION_SIZE // 2
PLAYER_WEAPON_SLOTS = 12
PLAYER_MAX_HEALTH = 100.0
PLAYER_HIT_FLASH_TICKS = 6
CAMERA_LOOK_AHEAD_DISTANCE = 25.0
DEFAULT_AIM_DISTANCE = 10.0
FIRE_ANIMATION_TICKS = 3
SHOT_EFFECT_TICKS = 3
DEFAULT_SHOT_TRACE_DISTANCE = 170
MELEE_SHOT_TRACE_DISTANCE = 34
SHOT_TRACE_STEP = 4


@dataclass(frozen=True, slots=True)
class WeaponProfile:
    loading_time: int
    is_gun: bool


@dataclass(frozen=True, slots=True)
class ShotEvent:
    origin_x: float
    origin_y: float
    angle: int
    max_distance: int
    weapon_slot: int
    impact_x: int
    impact_y: int


WEAPON_PROFILES: tuple[WeaponProfile, ...] = (
    WeaponProfile(loading_time=10, is_gun=False),
    WeaponProfile(loading_time=10, is_gun=True),
    WeaponProfile(loading_time=17, is_gun=True),
    WeaponProfile(loading_time=4, is_gun=True),
    WeaponProfile(loading_time=5, is_gun=True),
    WeaponProfile(loading_time=30, is_gun=True),
    WeaponProfile(loading_time=10, is_gun=True),
    WeaponProfile(loading_time=40, is_gun=True),
    WeaponProfile(loading_time=5, is_gun=True),
    WeaponProfile(loading_time=10, is_gun=False),
    WeaponProfile(loading_time=1, is_gun=True),
    WeaponProfile(loading_time=20, is_gun=False),
)

WEAPON_BULLET_TYPE: tuple[int, ...] = (
    0,
    1,
    3,
    1,
    2,
    5,
    4,
    6,
    3,
    7,
    8,
    9,
)

BULLET_TYPE_MAX_UNITS: tuple[int, ...] = (
    300,
    300,
    300,
    150,
    125,
    100,
    100,
    3000,
    100,
)


def _default_weapon_slots() -> list[bool]:
    slots = [False] * PLAYER_WEAPON_SLOTS
    slots[0] = True
    return slots


def _default_bullet_amounts() -> list[int]:
    return [0] * DIFF_BULLETS


@dataclass(slots=True)
class PlayerState:
    x: float
    y: float
    angle: int = 0
    speed: float = PLAYER_BASE_SPEED
    max_health: float = PLAYER_MAX_HEALTH
    health: float = PLAYER_MAX_HEALTH
    dead: bool = False
    current_weapon: int = 0
    weapons: list[bool] = field(default_factory=_default_weapon_slots)
    bullets: list[int] = field(default_factory=_default_bullet_amounts)
    load_count: int = 0
    shoot_hold_count: int = 0
    fire_animation_ticks: int = 0
    hit_flash_ticks: int = 0
    shot_effect_ticks: int = 0
    shot_effect_x: int = 0
    shot_effect_y: int = 0
    shots_fired_total: int = 0
    hits_taken_total: int = 0
    damage_taken_total: float = 0.0
    walking: bool = False
    pending_shots: list[ShotEvent] = field(default_factory=list)

    @property
    def center_x(self) -> float:
        return self.x + PLAYER_CENTER_OFFSET

    @property
    def center_y(self) -> float:
        return self.y + PLAYER_CENTER_OFFSET

    def grant_weapon(self, slot: int) -> None:
        if 0 <= slot < len(self.weapons):
            self.weapons[slot] = True

    @property
    def current_weapon_profile(self) -> WeaponProfile:
        return weapon_profile_for_slot(self.current_weapon)

    @property
    def current_weapon_is_gun(self) -> bool:
        return self.current_weapon_profile.is_gun


def spawn_player_from_level(level: LevelData, player_index: int = 0) -> PlayerState:
    index = 0 if player_index <= 0 else 1
    return PlayerState(
        x=float(level.player_start_x[index] * TILE_SIZE),
        y=float(level.player_start_y[index] * TILE_SIZE),
    )


def weapon_profile_for_slot(weapon_slot: int) -> WeaponProfile:
    if 0 <= weapon_slot < len(WEAPON_PROFILES):
        return WEAPON_PROFILES[weapon_slot]
    return WEAPON_PROFILES[0]


def weapon_bullet_type_index_for_slot(weapon_slot: int) -> int | None:
    if 0 <= weapon_slot < len(WEAPON_BULLET_TYPE):
        bullet_type = WEAPON_BULLET_TYPE[weapon_slot]
        if bullet_type > 0:
            return bullet_type - 1
    return None


def bullet_capacity_units_for_type(bullet_type_index: int) -> int:
    if 0 <= bullet_type_index < len(BULLET_TYPE_MAX_UNITS):
        return BULLET_TYPE_MAX_UNITS[bullet_type_index]
    return BULLET_TYPE_MAX_UNITS[0]


def grant_bullet_ammo(player: PlayerState, bullet_type_index: int, amount: int) -> int:
    if amount <= 0:
        return 0
    if bullet_type_index < 0 or bullet_type_index >= len(player.bullets):
        return 0

    capacity = bullet_capacity_units_for_type(bullet_type_index)
    current = max(0, player.bullets[bullet_type_index])
    gained = min(amount, max(0, capacity - current))
    if gained <= 0:
        return 0

    player.bullets[bullet_type_index] = current + gained
    return gained


def current_weapon_has_ammo(player: PlayerState) -> bool:
    bullet_type = weapon_bullet_type_index_for_slot(player.current_weapon)
    if bullet_type is None:
        return True
    if bullet_type >= len(player.bullets):
        return False
    return player.bullets[bullet_type] > 0


def consume_current_weapon_ammo(player: PlayerState) -> bool:
    bullet_type = weapon_bullet_type_index_for_slot(player.current_weapon)
    if bullet_type is None:
        return True
    if bullet_type >= len(player.bullets):
        return False
    if player.bullets[bullet_type] <= 0:
        return False

    player.bullets[bullet_type] -= 1
    return True


def apply_player_controls(
    player: PlayerState,
    level: LevelData,
    held_actions: Iterable[InputAction],
    *,
    cycle_weapon: bool = False,
    select_weapon_slot: int | None = None,
) -> None:
    _decay_player_effects(player)

    if player.dead:
        player.walking = False
        return

    active = set(held_actions)
    speed_i = player.speed
    walked = False

    has_strafe_modifier = InputAction.STRAFE_MODIFIER in active

    if InputAction.TURN_LEFT in active and not has_strafe_modifier:
        rotate_player(player, PLAYER_ROTATION_STEP_DEGREES)
    if (has_strafe_modifier and InputAction.TURN_LEFT in active) or InputAction.STRAFE_LEFT in active:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 90) % 360,
            speed=player.speed * 0.9,
        )
        speed_i = player.speed * 0.8
        walked = True

    if InputAction.TURN_RIGHT in active and not has_strafe_modifier:
        rotate_player(player, -PLAYER_ROTATION_STEP_DEGREES)
    if (has_strafe_modifier and InputAction.TURN_RIGHT in active) or InputAction.STRAFE_RIGHT in active:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 270) % 360,
            speed=player.speed * 0.9,
        )
        speed_i = player.speed * 0.8
        walked = True

    if InputAction.MOVE_FORWARD in active:
        move_player_with_collision(player, level, angle=player.angle, speed=speed_i)
        walked = True
    if InputAction.MOVE_BACKWARD in active:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 180) % 360,
            speed=0.75 * speed_i,
        )
        walked = True

    player.walking = walked

    _handle_shoot_input(player, level, active)

    weapon_changed = False
    if cycle_weapon:
        weapon_changed = cycle_weapon_slot(player) or weapon_changed
    if select_weapon_slot is not None:
        weapon_changed = select_weapon_slot_if_owned(player, select_weapon_slot) or weapon_changed

    if weapon_changed:
        player.load_count = 0

    _advance_reload_counter(player)


def rotate_player(player: PlayerState, change: int) -> None:
    player.angle = (player.angle + change) % 360


def cycle_weapon_slot(player: PlayerState) -> bool:
    if not player.weapons:
        return False

    slot = (player.current_weapon + 1) % len(player.weapons)
    for _ in range(len(player.weapons)):
        if player.weapons[slot]:
            if slot == player.current_weapon:
                return False
            player.current_weapon = slot
            return True
        slot = (slot + 1) % len(player.weapons)
    return False


def select_weapon_slot_if_owned(player: PlayerState, weapon_slot: int) -> bool:
    if weapon_slot < 0 or weapon_slot >= len(player.weapons):
        return False
    if player.weapons[weapon_slot]:
        if player.current_weapon == weapon_slot:
            return False
        player.current_weapon = weapon_slot
        return True
    return False


def trace_shot_impact(
    level: LevelData,
    *,
    origin_x: float,
    origin_y: float,
    angle: int,
    max_distance: int,
    step: int = SHOT_TRACE_STEP,
) -> tuple[int, int]:
    angle_radians = math.radians(angle % 360)

    px = int(origin_x)
    py = int(origin_y)
    for distance in range(0, max_distance + 1, max(1, step)):
        x = int(origin_x + (distance * math.sin(angle_radians)))
        y = int(origin_y + (distance * math.cos(angle_radians)))
        if not _is_floor_pixel(level, x, y):
            return px, py
        px = x
        py = y
    return px, py


def consume_pending_shots(player: PlayerState) -> tuple[ShotEvent, ...]:
    if not player.pending_shots:
        return ()
    shots = tuple(player.pending_shots)
    player.pending_shots.clear()
    return shots


def apply_player_damage(player: PlayerState, damage: float) -> bool:
    if damage <= 0 or player.dead:
        return False

    player.health -= damage
    if player.health < 0:
        player.health = 0.0
    player.hit_flash_ticks = PLAYER_HIT_FLASH_TICKS
    player.hits_taken_total += 1
    player.damage_taken_total += damage
    if player.health <= 0:
        player.dead = True
        return True
    return False


def _handle_shoot_input(player: PlayerState, level: LevelData, active: set[InputAction]) -> None:
    if InputAction.SHOOT in active:
        if player.load_count >= player.current_weapon_profile.loading_time:
            if current_weapon_has_ammo(player):
                _fire_weapon(player, level)
            elif player.current_weapon != 0:
                player.current_weapon = 0
                player.load_count = 0
        player.shoot_hold_count += 1
    else:
        player.shoot_hold_count = 0


def _fire_weapon(player: PlayerState, level: LevelData) -> None:
    if not consume_current_weapon_ammo(player):
        return

    angle_radians = math.radians(player.angle)
    origin_x = player.center_x + (10.0 * math.sin(angle_radians))
    origin_y = player.center_y + (10.0 * math.cos(angle_radians))

    max_distance = (
        DEFAULT_SHOT_TRACE_DISTANCE
        if player.current_weapon_is_gun
        else MELEE_SHOT_TRACE_DISTANCE
    )
    impact_x, impact_y = trace_shot_impact(
        level,
        origin_x=origin_x,
        origin_y=origin_y,
        angle=player.angle,
        max_distance=max_distance,
    )

    player.shots_fired_total += 1
    player.load_count = 0
    player.fire_animation_ticks = FIRE_ANIMATION_TICKS
    player.shot_effect_ticks = SHOT_EFFECT_TICKS
    player.shot_effect_x = impact_x
    player.shot_effect_y = impact_y
    player.pending_shots.append(
        ShotEvent(
            origin_x=origin_x,
            origin_y=origin_y,
            angle=player.angle,
            max_distance=max_distance,
            weapon_slot=player.current_weapon,
            impact_x=impact_x,
            impact_y=impact_y,
        ),
    )


def _advance_reload_counter(player: PlayerState) -> None:
    loading_time = player.current_weapon_profile.loading_time
    if player.load_count < loading_time:
        player.load_count += 1


def _decay_player_effects(player: PlayerState) -> None:
    if player.fire_animation_ticks > 0:
        player.fire_animation_ticks -= 1
    if player.hit_flash_ticks > 0:
        player.hit_flash_ticks -= 1
    if player.shot_effect_ticks > 0:
        player.shot_effect_ticks -= 1


def move_player_with_collision(
    player: PlayerState,
    level: LevelData,
    *,
    angle: int,
    speed: float,
) -> None:
    angle_radians = math.radians(angle % 360)

    new_x = player.x + (speed * math.sin(angle_radians))
    new_y = player.y + (speed * math.cos(angle_radians))

    rnx = int(new_x)
    rny = int(new_y)
    edge = 6
    edge2 = 4

    if new_y < player.y:
        if _is_floor_pair(
            level,
            x1=rnx + 14 - edge2,
            y1=rny + edge,
            x2=rnx + 14 + edge2,
            y2=rny + edge,
        ):
            player.y = new_y

    if new_y > player.y:
        if _is_floor_pair(
            level,
            x1=rnx + 14 - edge2,
            y1=rny + 28 - edge,
            x2=rnx + 14 + edge2,
            y2=rny + 28 - edge,
        ):
            player.y = new_y

    if new_x < player.x:
        if _is_floor_pair(
            level,
            x1=rnx + edge,
            y1=rny + 14 - edge2,
            x2=rnx + edge,
            y2=rny + 14 + edge2,
        ):
            player.x = new_x

    if new_x > player.x:
        if _is_floor_pair(
            level,
            x1=rnx + 28 - edge,
            y1=rny + 14 - edge2,
            x2=rnx + 28 - edge,
            y2=rny + 14 + edge2,
        ):
            player.x = new_x


def follow_player_camera(
    *,
    camera_x: int,
    camera_y: int,
    player: PlayerState,
    max_camera_x: int,
    max_camera_y: int,
) -> tuple[int, int]:
    center_x = player.center_x
    center_y = player.center_y
    half_width = SCREEN_WIDTH // 2
    half_height = SCREEN_HEIGHT // 2
    angle_radians = math.radians(player.angle)

    if abs((camera_x + half_width) - center_x) > half_width:
        camera_x = int(player.x) - half_width

    look_x = center_x + (CAMERA_LOOK_AHEAD_DISTANCE * math.sin(angle_radians))
    speed_x = int(abs((camera_x + half_width) - look_x) / 4)
    if camera_x + half_width < look_x:
        camera_x += speed_x
    if camera_x + half_width > look_x:
        camera_x -= speed_x
    camera_x = _clamp(camera_x, 0, max_camera_x)

    if abs((camera_y + half_height) - center_y) > 120:
        camera_y = int(player.y) - half_height

    look_y = center_y + (CAMERA_LOOK_AHEAD_DISTANCE * math.cos(angle_radians))
    speed_y = int(abs((camera_y + half_height) - look_y) / 4)
    if camera_y + half_height < look_y:
        camera_y += speed_y
    if camera_y + half_height > look_y:
        camera_y -= speed_y
    camera_y = _clamp(camera_y, 0, max_camera_y)

    return camera_x, camera_y


def aim_point_from_player(player: PlayerState, distance: float = DEFAULT_AIM_DISTANCE) -> tuple[int, int]:
    angle_radians = math.radians(player.angle)
    x = player.center_x + (distance * math.sin(angle_radians))
    y = player.center_y + (distance * math.cos(angle_radians))
    return int(x), int(y)


def _is_floor_pair(level: LevelData, *, x1: int, y1: int, x2: int, y2: int) -> bool:
    return _is_floor_pixel(level, x1, y1) and _is_floor_pixel(level, x2, y2)


def _is_floor_pixel(level: LevelData, x: int, y: int) -> bool:
    if x < 0 or y < 0:
        return False

    tile_x = x // TILE_SIZE
    tile_y = y // TILE_SIZE
    if tile_x < 0 or tile_x >= level.level_x_size or tile_y < 0 or tile_y >= level.level_y_size:
        return False

    block = level.blocks[tile_y * level.level_x_size + tile_x]
    return block.type == FLOOR_BLOCK_TYPE


def _clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value
