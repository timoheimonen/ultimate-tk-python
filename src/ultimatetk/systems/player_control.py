from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Iterable

from ultimatetk.core.events import InputAction
from ultimatetk.formats.lev import DIFF_BULLETS, DIFF_WEAPONS, LevelData
from ultimatetk.rendering.constants import FLOOR_BLOCK_TYPE, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE


PLAYER_ROTATION_STEP_DEGREES = 9
PLAYER_BASE_SPEED = 2.0
PLAYER_COLLISION_SIZE = 28
PLAYER_CENTER_OFFSET = PLAYER_COLLISION_SIZE // 2
PLAYER_WEAPON_SLOTS = 12
PLAYER_MAX_HEALTH = 100.0
PLAYER_HIT_FLASH_TICKS = 6
CAMERA_LOOK_AHEAD_DISTANCE = 25.0
CAMERA_WALK_LOOK_BOOST = 4.0
CAMERA_DEAD_ZONE_X = 6
CAMERA_DEAD_ZONE_Y = 4
CAMERA_IDLE_DEAD_ZONE_X_BONUS = 4
CAMERA_IDLE_DEAD_ZONE_Y_BONUS = 2
CAMERA_ACTION_DEAD_ZONE_X_BONUS = 1
CAMERA_ACTION_DEAD_ZONE_Y_BONUS = 1
CAMERA_CATCHUP_DIVISOR = 4
CAMERA_ACTION_IDLE_CATCHUP_BONUS = 2
CAMERA_MAX_STEP = 16
CAMERA_STRAFE_TURN_DEAD_ZONE_X_REDUCTION = 2
CAMERA_STRAFE_TURN_DEAD_ZONE_Y_REDUCTION = 1
CAMERA_EDGE_RELEASE_DEAD_ZONE = 0
DEFAULT_AIM_DISTANCE = 10.0
FIRE_ANIMATION_TICKS = 3
SHOT_EFFECT_TICKS = 3
DEFAULT_SHOT_TRACE_DISTANCE = 170
MELEE_SHOT_TRACE_DISTANCE = 34
SHOT_TRACE_STEP = 4

PLAYER_COLLISION_EDGE = 6
PLAYER_COLLISION_CENTER_INSET = 4
SHIELD_HEALTH_BONUS_PER_LEVEL = 10.0


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


@dataclass(frozen=True, slots=True)
class ShopSellPriceTable:
    weapon_slots: tuple[int, ...]
    shield_base: int
    target_system: int


@dataclass(frozen=True, slots=True)
class ShopTransactionEvent:
    action: str
    category: str
    row: int
    column: int
    success: bool
    units: int
    cash_delta: int
    reason: str = ""


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

WEAPON_SHOP_COSTS: tuple[int, ...] = (
    0,
    400,
    1000,
    2000,
    4000,
    4000,
    6000,
    6000,
    6000,
    1000,
    3000,
    1000,
)

WEAPON_SHOP_NAMES: tuple[str, ...] = (
    "Fist",
    "Pistola",
    "Shotgun",
    "Uzi",
    "Auto rifle",
    "Grenade launcher",
    "Auto grenadier",
    "Heavy launcher",
    "Auto shotgun",
    "C4-Activator",
    "Flame thrower",
    "Mine dropper",
)

WEAPON_SHOP_SHORT_LABELS: tuple[str, ...] = (
    "FI",
    "P9",
    "SG",
    "UZ",
    "AR",
    "GL",
    "AG",
    "HL",
    "AS",
    "C4",
    "FL",
    "MN",
)

SHOP_SHIELD_BASE_COST = 160
SHOP_SHIELD_LEVEL_COST_STEP = 15
SHOP_SHIELD_MAX_LEVEL = 30
SHOP_TARGET_SYSTEM_COST = 500

SHOP_ROW_WEAPONS = 0
SHOP_ROW_AMMO = 1
SHOP_ROW_OTHER = 2
SHOP_ROW_COLUMN_COUNTS: tuple[int, ...] = (
    DIFF_WEAPONS,
    DIFF_BULLETS,
    2,
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

BULLET_TYPE_SHOP_COSTS: tuple[int, ...] = (
    3,
    5,
    6,
    70,
    100,
    200,
    150,
    6,
    150,
)

BULLET_TYPE_SHOP_UNITS_PER_PURCHASE: tuple[int, ...] = (
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    10,
    1,
)

BULLET_TYPE_SHOP_NAMES: tuple[str, ...] = (
    "9mm bullets",
    "12mm bullets",
    "Shotgun shells",
    "Light grenades",
    "Medium grenades",
    "Heavy grenades",
    "C4-explosives",
    "Gas",
    "Mines",
)

BULLET_TYPE_SHOP_SHORT_LABELS: tuple[str, ...] = (
    "9M",
    "12",
    "SH",
    "LG",
    "MG",
    "HG",
    "C4",
    "GS",
    "MN",
)

SHOP_BLOCK_REASON_NONE = ""
SHOP_BLOCK_REASON_NO_CASH = "NO CASH"
SHOP_BLOCK_REASON_OWNED = "OWNED"
SHOP_BLOCK_REASON_NOT_OWNED = "NOT OWNED"
SHOP_BLOCK_REASON_FULL = "FULL"
SHOP_BLOCK_REASON_NO_STOCK = "NO STOCK"
SHOP_BLOCK_REASON_MAX_LEVEL = "MAX LEVEL"
SHOP_BLOCK_REASON_NO_SHIELD = "NO SHIELD"
SHOP_BLOCK_REASON_TARGET_ON = "TARGET ON"
SHOP_BLOCK_REASON_TARGET_OFF = "TARGET OFF"
SHOP_BLOCK_REASON_INVALID = "INVALID"


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
    cash: int = 0
    shield: int = 0
    target_system_enabled: bool = False
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
    moving_forward: bool = False
    moving_backward: bool = False
    strafing: bool = False
    turning: bool = False
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


def player_health_capacity(player: PlayerState) -> float:
    return max(0.0, player.max_health + (max(0, player.shield) * SHIELD_HEALTH_BONUS_PER_LEVEL))


def clamp_player_health_to_capacity(player: PlayerState) -> float:
    capacity = player_health_capacity(player)
    if player.health > capacity:
        player.health = capacity
    if player.health < 0.0:
        player.health = 0.0
    return capacity


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


def weapon_shop_cost_for_slot(weapon_slot: int) -> int:
    if 0 <= weapon_slot < len(WEAPON_SHOP_COSTS):
        return WEAPON_SHOP_COSTS[weapon_slot]
    return WEAPON_SHOP_COSTS[0]


def weapon_shop_name_for_slot(weapon_slot: int) -> str:
    if 0 <= weapon_slot < len(WEAPON_SHOP_NAMES):
        return WEAPON_SHOP_NAMES[weapon_slot]
    if weapon_slot > 0:
        return f"Weapon {weapon_slot}"
    return WEAPON_SHOP_NAMES[0]


def weapon_shop_short_label_for_slot(weapon_slot: int) -> str:
    if 0 <= weapon_slot < len(WEAPON_SHOP_SHORT_LABELS):
        return WEAPON_SHOP_SHORT_LABELS[weapon_slot]
    return "??"


def bullet_capacity_units_for_type(bullet_type_index: int) -> int:
    if 0 <= bullet_type_index < len(BULLET_TYPE_MAX_UNITS):
        return BULLET_TYPE_MAX_UNITS[bullet_type_index]
    return BULLET_TYPE_MAX_UNITS[0]


def bullet_shop_cost_for_type(bullet_type_index: int) -> int:
    if 0 <= bullet_type_index < len(BULLET_TYPE_SHOP_COSTS):
        return BULLET_TYPE_SHOP_COSTS[bullet_type_index]
    return BULLET_TYPE_SHOP_COSTS[0]


def bullet_shop_units_for_type(bullet_type_index: int) -> int:
    if 0 <= bullet_type_index < len(BULLET_TYPE_SHOP_UNITS_PER_PURCHASE):
        return BULLET_TYPE_SHOP_UNITS_PER_PURCHASE[bullet_type_index]
    return BULLET_TYPE_SHOP_UNITS_PER_PURCHASE[0]


def bullet_shop_name_for_type(bullet_type_index: int) -> str:
    if 0 <= bullet_type_index < len(BULLET_TYPE_SHOP_NAMES):
        return BULLET_TYPE_SHOP_NAMES[bullet_type_index]
    if bullet_type_index >= 0:
        return f"Ammo {bullet_type_index + 1}"
    return "Ammo"


def bullet_shop_short_label_for_type(bullet_type_index: int) -> str:
    if 0 <= bullet_type_index < len(BULLET_TYPE_SHOP_SHORT_LABELS):
        return BULLET_TYPE_SHOP_SHORT_LABELS[bullet_type_index]
    return "??"


def shop_column_count_for_row(row: int) -> int:
    if 0 <= row < len(SHOP_ROW_COLUMN_COUNTS):
        return SHOP_ROW_COLUMN_COUNTS[row]
    return SHOP_ROW_COLUMN_COUNTS[SHOP_ROW_WEAPONS]


def clamp_shop_selection(row: int, column: int) -> tuple[int, int]:
    max_row = len(SHOP_ROW_COLUMN_COUNTS) - 1
    clamped_row = min(max(0, row), max_row)
    max_column = max(1, shop_column_count_for_row(clamped_row))
    clamped_column = min(max(0, column), max_column - 1)
    return clamped_row, clamped_column


def move_shop_selection(
    row: int,
    column: int,
    *,
    row_delta: int = 0,
    column_delta: int = 0,
) -> tuple[int, int]:
    return clamp_shop_selection(
        row + row_delta,
        column + column_delta,
    )


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


def buy_bullet_ammo_from_shop(player: PlayerState, bullet_type_index: int) -> int:
    if bullet_type_index < 0 or bullet_type_index >= len(player.bullets):
        return 0

    cost = max(0, bullet_shop_cost_for_type(bullet_type_index))
    if player.cash < cost:
        return 0

    amount = max(0, bullet_shop_units_for_type(bullet_type_index))
    gained = grant_bullet_ammo(player, bullet_type_index, amount)
    if gained <= 0:
        return 0

    player.cash -= cost
    return gained


def sell_bullet_ammo_to_shop(player: PlayerState, bullet_type_index: int) -> int:
    if bullet_type_index < 0 or bullet_type_index >= len(player.bullets):
        return 0

    current = max(0, player.bullets[bullet_type_index])
    if current <= 0:
        return 0

    amount = max(1, bullet_shop_units_for_type(bullet_type_index))
    sold = min(current, amount)
    player.bullets[bullet_type_index] = current - sold
    player.cash += max(0, bullet_shop_cost_for_type(bullet_type_index))
    return sold


def generate_shop_sell_prices(*, random_seed: int | None = None) -> ShopSellPriceTable:
    rng = random.Random(random_seed)

    weapon_sell_prices: list[int] = []
    for weapon_slot in range(1, DIFF_WEAPONS + 1):
        cost = max(0, weapon_shop_cost_for_slot(weapon_slot))
        random_range = max(1, cost // 2)
        value = int(0.8 * cost) - rng.randrange(random_range)
        weapon_sell_prices.append(max(0, value))

    shield_random = max(1, SHOP_SHIELD_BASE_COST // 2)
    shield_base = int(0.8 * SHOP_SHIELD_BASE_COST) - rng.randrange(shield_random)

    target_random = max(1, SHOP_TARGET_SYSTEM_COST // 2)
    target_system = int(0.8 * SHOP_TARGET_SYSTEM_COST) - rng.randrange(target_random)

    return ShopSellPriceTable(
        weapon_slots=tuple(max(0, value) for value in weapon_sell_prices),
        shield_base=max(0, shield_base),
        target_system=max(0, target_system),
    )


def weapon_sell_price_for_slot(sell_prices: ShopSellPriceTable, weapon_slot: int) -> int:
    if weapon_slot <= 0:
        return 0
    if weapon_slot > len(sell_prices.weapon_slots):
        return 0
    return max(0, sell_prices.weapon_slots[weapon_slot - 1])


def buy_weapon_from_shop(player: PlayerState, weapon_slot: int) -> bool:
    if weapon_slot <= 0 or weapon_slot >= len(player.weapons):
        return False
    if player.weapons[weapon_slot]:
        return False

    cost = max(0, weapon_shop_cost_for_slot(weapon_slot))
    if player.cash < cost:
        return False

    player.weapons[weapon_slot] = True
    player.cash -= cost
    return True


def sell_weapon_to_shop(player: PlayerState, weapon_slot: int, sell_prices: ShopSellPriceTable) -> bool:
    if weapon_slot <= 0 or weapon_slot >= len(player.weapons):
        return False
    if not player.weapons[weapon_slot]:
        return False

    player.weapons[weapon_slot] = False
    if player.current_weapon == weapon_slot:
        player.current_weapon = 0
        player.load_count = 0

    player.cash += weapon_sell_price_for_slot(sell_prices, weapon_slot)
    return True


def shield_shop_buy_cost_for_level(shield_level: int) -> int:
    return SHOP_SHIELD_BASE_COST + max(0, shield_level) * SHOP_SHIELD_LEVEL_COST_STEP


def buy_shield_from_shop(player: PlayerState) -> bool:
    if player.shield >= SHOP_SHIELD_MAX_LEVEL:
        return False

    cost = shield_shop_buy_cost_for_level(player.shield)
    if player.cash < cost:
        return False

    player.cash -= cost
    player.shield += 1
    return True


def sell_shield_to_shop(player: PlayerState, sell_prices: ShopSellPriceTable) -> bool:
    if player.shield <= 0:
        return False

    prior_level = max(0, player.shield - 1)
    player.cash += max(0, sell_prices.shield_base)
    player.cash += (SHOP_SHIELD_LEVEL_COST_STEP * prior_level) // 2
    player.shield -= 1
    clamp_player_health_to_capacity(player)
    return True


def buy_target_system_from_shop(player: PlayerState) -> bool:
    if player.target_system_enabled:
        return False
    if player.cash < SHOP_TARGET_SYSTEM_COST:
        return False

    player.target_system_enabled = True
    player.cash -= SHOP_TARGET_SYSTEM_COST
    return True


def sell_target_system_to_shop(player: PlayerState, sell_prices: ShopSellPriceTable) -> bool:
    if not player.target_system_enabled:
        return False

    player.target_system_enabled = False
    player.cash += max(0, sell_prices.target_system)
    return True


def buy_selected_shop_item(player: PlayerState, row: int, column: int) -> ShopTransactionEvent:
    row, column = clamp_shop_selection(row, column)
    cash_before = player.cash
    reason = SHOP_BLOCK_REASON_NONE

    if row == SHOP_ROW_WEAPONS:
        weapon_slot = column + 1
        if weapon_slot <= 0 or weapon_slot >= len(player.weapons):
            reason = SHOP_BLOCK_REASON_INVALID
        elif player.weapons[weapon_slot]:
            reason = SHOP_BLOCK_REASON_OWNED
        elif player.cash < weapon_shop_cost_for_slot(weapon_slot):
            reason = SHOP_BLOCK_REASON_NO_CASH

        success = buy_weapon_from_shop(player, column + 1)
        units = 1 if success else 0
        category = "weapon"
    elif row == SHOP_ROW_AMMO:
        if column < 0 or column >= len(player.bullets):
            reason = SHOP_BLOCK_REASON_INVALID
        elif player.cash < bullet_shop_cost_for_type(column):
            reason = SHOP_BLOCK_REASON_NO_CASH
        else:
            capacity = bullet_capacity_units_for_type(column)
            current = max(0, player.bullets[column])
            if current >= capacity:
                reason = SHOP_BLOCK_REASON_FULL

        units = buy_bullet_ammo_from_shop(player, column)
        success = units > 0
        category = "ammo"
    elif column == 0:
        if player.shield >= SHOP_SHIELD_MAX_LEVEL:
            reason = SHOP_BLOCK_REASON_MAX_LEVEL
        elif player.cash < shield_shop_buy_cost_for_level(player.shield):
            reason = SHOP_BLOCK_REASON_NO_CASH

        success = buy_shield_from_shop(player)
        units = 1 if success else 0
        category = "shield"
    else:
        if player.target_system_enabled:
            reason = SHOP_BLOCK_REASON_TARGET_ON
        elif player.cash < SHOP_TARGET_SYSTEM_COST:
            reason = SHOP_BLOCK_REASON_NO_CASH

        success = buy_target_system_from_shop(player)
        units = 1 if success else 0
        category = "target"

    if success:
        reason = SHOP_BLOCK_REASON_NONE

    return ShopTransactionEvent(
        action="buy",
        category=category,
        row=row,
        column=column,
        success=success,
        units=units,
        cash_delta=player.cash - cash_before,
        reason=reason,
    )


def sell_selected_shop_item(
    player: PlayerState,
    row: int,
    column: int,
    sell_prices: ShopSellPriceTable,
) -> ShopTransactionEvent:
    row, column = clamp_shop_selection(row, column)
    cash_before = player.cash
    reason = SHOP_BLOCK_REASON_NONE

    if row == SHOP_ROW_WEAPONS:
        weapon_slot = column + 1
        if weapon_slot <= 0 or weapon_slot >= len(player.weapons):
            reason = SHOP_BLOCK_REASON_INVALID
        elif not player.weapons[weapon_slot]:
            reason = SHOP_BLOCK_REASON_NOT_OWNED

        success = sell_weapon_to_shop(player, column + 1, sell_prices)
        units = 1 if success else 0
        category = "weapon"
    elif row == SHOP_ROW_AMMO:
        if column < 0 or column >= len(player.bullets):
            reason = SHOP_BLOCK_REASON_INVALID
        elif player.bullets[column] <= 0:
            reason = SHOP_BLOCK_REASON_NO_STOCK

        units = sell_bullet_ammo_to_shop(player, column)
        success = units > 0
        category = "ammo"
    elif column == 0:
        if player.shield <= 0:
            reason = SHOP_BLOCK_REASON_NO_SHIELD

        success = sell_shield_to_shop(player, sell_prices)
        units = 1 if success else 0
        category = "shield"
    else:
        if not player.target_system_enabled:
            reason = SHOP_BLOCK_REASON_TARGET_OFF

        success = sell_target_system_to_shop(player, sell_prices)
        units = 1 if success else 0
        category = "target"

    if success:
        reason = SHOP_BLOCK_REASON_NONE

    return ShopTransactionEvent(
        action="sell",
        category=category,
        row=row,
        column=column,
        success=success,
        units=units,
        cash_delta=player.cash - cash_before,
        reason=reason,
    )


def current_weapon_ammo_snapshot(player: PlayerState) -> tuple[int, int, int]:
    bullet_type = weapon_bullet_type_index_for_slot(player.current_weapon)
    if bullet_type is None:
        return -1, 0, 0
    if bullet_type < 0 or bullet_type >= len(player.bullets):
        return -1, 0, 0

    capacity = bullet_capacity_units_for_type(bullet_type)
    current = max(0, min(player.bullets[bullet_type], capacity))
    return bullet_type, current, capacity


def bullet_ammo_capacities_snapshot() -> tuple[int, ...]:
    return tuple(bullet_capacity_units_for_type(index) for index in range(DIFF_BULLETS))


def bullet_ammo_pools_snapshot(player: PlayerState) -> tuple[int, ...]:
    pools: list[int] = []
    for index in range(DIFF_BULLETS):
        capacity = bullet_capacity_units_for_type(index)
        units = player.bullets[index] if index < len(player.bullets) else 0
        pools.append(max(0, min(units, capacity)))
    return tuple(pools)


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
        player.moving_forward = False
        player.moving_backward = False
        player.strafing = False
        player.turning = False
        return

    active = set(held_actions)
    speed_i = player.speed
    walked = False

    has_strafe_modifier = InputAction.STRAFE_MODIFIER in active
    turning_left = InputAction.TURN_LEFT in active and not has_strafe_modifier
    turning_right = InputAction.TURN_RIGHT in active and not has_strafe_modifier
    strafe_left = (has_strafe_modifier and InputAction.TURN_LEFT in active) or InputAction.STRAFE_LEFT in active
    strafe_right = (has_strafe_modifier and InputAction.TURN_RIGHT in active) or InputAction.STRAFE_RIGHT in active
    moving_forward = InputAction.MOVE_FORWARD in active
    moving_backward = InputAction.MOVE_BACKWARD in active

    player.turning = turning_left or turning_right
    player.strafing = strafe_left or strafe_right
    player.moving_forward = moving_forward
    player.moving_backward = moving_backward

    if turning_left:
        rotate_player(player, PLAYER_ROTATION_STEP_DEGREES)
    if strafe_left:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 90) % 360,
            speed=player.speed * 0.9,
        )
        speed_i = player.speed * 0.8
        walked = True

    if turning_right:
        rotate_player(player, -PLAYER_ROTATION_STEP_DEGREES)
    if strafe_right:
        move_player_with_collision(
            player,
            level,
            angle=(player.angle + 270) % 360,
            speed=player.speed * 0.9,
        )
        speed_i = player.speed * 0.8
        walked = True

    if moving_forward:
        move_player_with_collision(player, level, angle=player.angle, speed=speed_i)
        walked = True
    if moving_backward:
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

    move_x = speed * math.sin(angle_radians)
    move_y = speed * math.cos(angle_radians)

    edge = PLAYER_COLLISION_EDGE
    center_inset = PLAYER_COLLISION_CENTER_INSET

    if move_y != 0.0:
        new_y = player.y + move_y
        rny = int(new_y)
        rnx = int(player.x)
        if new_y < player.y:
            if _is_floor_triplet(
                level,
                x1=rnx + 14 - center_inset,
                y1=rny + edge,
                x2=rnx + 14 + center_inset,
                y2=rny + edge,
                x3=rnx + 14,
                y3=rny + edge,
            ):
                player.y = new_y
        if new_y > player.y:
            if _is_floor_triplet(
                level,
                x1=rnx + 14 - center_inset,
                y1=rny + 28 - edge,
                x2=rnx + 14 + center_inset,
                y2=rny + 28 - edge,
                x3=rnx + 14,
                y3=rny + 28 - edge,
            ):
                player.y = new_y

    if move_x != 0.0:
        new_x = player.x + move_x
        rnx = int(new_x)
        rny = int(player.y)
        if new_x < player.x:
            if _is_floor_triplet(
                level,
                x1=rnx + edge,
                y1=rny + 14 - center_inset,
                x2=rnx + edge,
                y2=rny + 14 + center_inset,
                x3=rnx + edge,
                y3=rny + 14,
            ):
                player.x = new_x
        if new_x > player.x:
            if _is_floor_triplet(
                level,
                x1=rnx + 28 - edge,
                y1=rny + 14 - center_inset,
                x2=rnx + 28 - edge,
                y2=rny + 14 + center_inset,
                x3=rnx + 28 - edge,
                y3=rny + 14,
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

    look_distance = CAMERA_LOOK_AHEAD_DISTANCE
    if player.walking and player.moving_forward and not player.moving_backward:
        look_distance += CAMERA_WALK_LOOK_BOOST
    elif player.walking and player.moving_backward and not player.moving_forward:
        look_distance = max(0.0, look_distance - CAMERA_WALK_LOOK_BOOST)

    look_x = center_x + (look_distance * math.sin(angle_radians))
    look_y = center_y + (look_distance * math.cos(angle_radians))
    target_camera_x = int(look_x) - half_width
    target_camera_y = int(look_y) - half_height

    dead_zone_x = CAMERA_DEAD_ZONE_X
    dead_zone_y = CAMERA_DEAD_ZONE_Y
    action_active = player.shoot_hold_count > 0 or player.fire_animation_ticks > 0
    if not player.walking and not action_active:
        dead_zone_x += CAMERA_IDLE_DEAD_ZONE_X_BONUS
        dead_zone_y += CAMERA_IDLE_DEAD_ZONE_Y_BONUS
    elif action_active:
        dead_zone_x += CAMERA_ACTION_DEAD_ZONE_X_BONUS
        dead_zone_y += CAMERA_ACTION_DEAD_ZONE_Y_BONUS

    catchup_divisor_x = CAMERA_CATCHUP_DIVISOR
    catchup_divisor_y = CAMERA_CATCHUP_DIVISOR

    if action_active and not player.walking:
        catchup_divisor_x = max(1, CAMERA_CATCHUP_DIVISOR - CAMERA_ACTION_IDLE_CATCHUP_BONUS)
        catchup_divisor_y = max(1, CAMERA_CATCHUP_DIVISOR - CAMERA_ACTION_IDLE_CATCHUP_BONUS)

    if player.walking and player.strafing and player.turning:
        dead_zone_x = max(0, dead_zone_x - CAMERA_STRAFE_TURN_DEAD_ZONE_X_REDUCTION)
        dead_zone_y = max(0, dead_zone_y - CAMERA_STRAFE_TURN_DEAD_ZONE_Y_REDUCTION)
        catchup_divisor_x = max(1, catchup_divisor_x - 1)

    dead_zone_x = _camera_edge_release_dead_zone(
        current=camera_x,
        target=target_camera_x,
        max_camera=max_camera_x,
        dead_zone=dead_zone_x,
    )
    dead_zone_y = _camera_edge_release_dead_zone(
        current=camera_y,
        target=target_camera_y,
        max_camera=max_camera_y,
        dead_zone=dead_zone_y,
    )

    if abs(camera_x - target_camera_x) > half_width:
        camera_x = target_camera_x
    else:
        camera_x = _approach_camera_axis(
            camera_x,
            target_camera_x,
            dead_zone=dead_zone_x,
            catchup_divisor=catchup_divisor_x,
        )

    if abs(camera_y - target_camera_y) > half_height:
        camera_y = target_camera_y
    else:
        camera_y = _approach_camera_axis(
            camera_y,
            target_camera_y,
            dead_zone=dead_zone_y,
            catchup_divisor=catchup_divisor_y,
        )

    camera_x = _clamp(camera_x, 0, max_camera_x)
    camera_y = _clamp(camera_y, 0, max_camera_y)

    return camera_x, camera_y


def aim_point_from_player(player: PlayerState, distance: float = DEFAULT_AIM_DISTANCE) -> tuple[int, int]:
    angle_radians = math.radians(player.angle)
    x = player.center_x + (distance * math.sin(angle_radians))
    y = player.center_y + (distance * math.cos(angle_radians))
    return int(x), int(y)


def _approach_camera_axis(
    current: int,
    target: int,
    *,
    dead_zone: int,
    catchup_divisor: int = CAMERA_CATCHUP_DIVISOR,
) -> int:
    delta = target - current
    abs_delta = abs(delta)
    if abs_delta <= max(0, dead_zone):
        return current

    step = max(1, abs_delta // max(1, catchup_divisor))
    step = min(step, CAMERA_MAX_STEP)
    if delta > 0:
        return current + step
    return current - step


def _camera_edge_release_dead_zone(*, current: int, target: int, max_camera: int, dead_zone: int) -> int:
    if dead_zone <= CAMERA_EDGE_RELEASE_DEAD_ZONE:
        return dead_zone
    if max_camera <= 0:
        return dead_zone

    if current <= 0 and target > 0:
        return CAMERA_EDGE_RELEASE_DEAD_ZONE
    if current >= max_camera and target < max_camera:
        return CAMERA_EDGE_RELEASE_DEAD_ZONE
    return dead_zone


def _is_floor_triplet(
    level: LevelData,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    x3: int,
    y3: int,
) -> bool:
    return _is_floor_pair(level, x1=x1, y1=y1, x2=x2, y2=y2) and _is_floor_pixel(level, x3, y3)


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
