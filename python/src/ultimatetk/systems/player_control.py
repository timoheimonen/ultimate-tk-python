from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from ultimatetk.core.events import InputAction
from ultimatetk.formats.lev import LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE


PLAYER_ROTATION_STEP_DEGREES = 9
PLAYER_BASE_SPEED = 2.0
PLAYER_COLLISION_SIZE = 28
PLAYER_CENTER_OFFSET = PLAYER_COLLISION_SIZE // 2
PLAYER_WEAPON_SLOTS = 12
CAMERA_LOOK_AHEAD_DISTANCE = 25.0
DEFAULT_AIM_DISTANCE = 10.0


def _default_weapon_slots() -> list[bool]:
    slots = [False] * PLAYER_WEAPON_SLOTS
    slots[0] = True
    return slots


@dataclass(slots=True)
class PlayerState:
    x: float
    y: float
    angle: int = 0
    speed: float = PLAYER_BASE_SPEED
    current_weapon: int = 0
    weapons: list[bool] = field(default_factory=_default_weapon_slots)

    @property
    def center_x(self) -> float:
        return self.x + PLAYER_CENTER_OFFSET

    @property
    def center_y(self) -> float:
        return self.y + PLAYER_CENTER_OFFSET

    def grant_weapon(self, slot: int) -> None:
        if 0 <= slot < len(self.weapons):
            self.weapons[slot] = True


def spawn_player_from_level(level: LevelData, player_index: int = 0) -> PlayerState:
    index = 0 if player_index <= 0 else 1
    return PlayerState(
        x=float(level.player_start_x[index] * TILE_SIZE),
        y=float(level.player_start_y[index] * TILE_SIZE),
    )


def apply_player_controls(
    player: PlayerState,
    level: LevelData,
    held_actions: Iterable[InputAction],
    *,
    cycle_weapon: bool = False,
    select_weapon_slot: int | None = None,
) -> None:
    active = set(held_actions)
    speed_i = player.speed

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

    if InputAction.MOVE_FORWARD in active:
        move_player_with_collision(player, level, angle=player.angle, speed=speed_i)
    if InputAction.MOVE_BACKWARD in active:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 180) % 360,
            speed=0.75 * speed_i,
        )

    if cycle_weapon:
        cycle_weapon_slot(player)
    if select_weapon_slot is not None:
        select_weapon_slot_if_owned(player, select_weapon_slot)


def rotate_player(player: PlayerState, change: int) -> None:
    player.angle = (player.angle + change) % 360


def cycle_weapon_slot(player: PlayerState) -> None:
    if not player.weapons:
        return

    slot = (player.current_weapon + 1) % len(player.weapons)
    for _ in range(len(player.weapons)):
        if player.weapons[slot]:
            player.current_weapon = slot
            return
        slot = (slot + 1) % len(player.weapons)


def select_weapon_slot_if_owned(player: PlayerState, weapon_slot: int) -> None:
    if weapon_slot < 0 or weapon_slot >= len(player.weapons):
        return
    if player.weapons[weapon_slot]:
        player.current_weapon = weapon_slot


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
