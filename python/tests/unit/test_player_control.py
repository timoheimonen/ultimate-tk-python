from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import InputAction
from ultimatetk.formats.lev import (
    DIFF_BULLETS,
    DIFF_ENEMIES,
    DIFF_WEAPONS,
    Block,
    CrateCounts,
    GeneralLevelInfo,
    LevelData,
)
from ultimatetk.systems.player_control import (
    PlayerState,
    ShopSellPriceTable,
    aim_point_from_player,
    apply_player_controls,
    bullet_ammo_capacities_snapshot,
    bullet_ammo_pools_snapshot,
    bullet_shop_cost_for_type,
    bullet_shop_units_for_type,
    buy_shield_from_shop,
    buy_target_system_from_shop,
    buy_bullet_ammo_from_shop,
    buy_weapon_from_shop,
    consume_pending_shots,
    current_weapon_ammo_snapshot,
    cycle_weapon_slot,
    follow_player_camera,
    generate_shop_sell_prices,
    grant_bullet_ammo,
    sell_shield_to_shop,
    sell_target_system_to_shop,
    sell_bullet_ammo_to_shop,
    sell_weapon_to_shop,
    select_weapon_slot_if_owned,
    shield_shop_buy_cost_for_level,
    spawn_player_from_level,
    weapon_sell_price_for_slot,
    weapon_shop_cost_for_slot,
)


def _build_level(
    *,
    width: int = 8,
    height: int = 8,
    walls: set[tuple[int, int]] | None = None,
    start: tuple[int, int] = (2, 2),
) -> LevelData:
    wall_tiles = walls or set()
    blocks = []
    for y in range(height):
        for x in range(width):
            block_type = 1 if (x, y) in wall_tiles else 0
            blocks.append(Block(type=block_type, num=0, shadow=0))

    crate_counts = CrateCounts(
        weapon_crates=tuple(0 for _ in range(DIFF_WEAPONS)),
        bullet_crates=tuple(0 for _ in range(DIFF_BULLETS)),
        energy_crates=0,
    )
    return LevelData(
        version=5,
        level_x_size=width,
        level_y_size=height,
        blocks=tuple(blocks),
        player_start_x=(start[0], start[0]),
        player_start_y=(start[1], start[1]),
        spots=(),
        steams=(),
        general_info=GeneralLevelInfo(comment="", time_limit=0, enemies=tuple(0 for _ in range(DIFF_ENEMIES))),
        normal_crate_counts=crate_counts,
        deathmatch_crate_counts=crate_counts,
        normal_crate_info=(),
        deathmatch_crate_info=(),
    )


class PlayerControlTests(unittest.TestCase):
    def test_spawn_player_from_level_uses_tile_coordinates(self) -> None:
        level = _build_level(start=(3, 4))
        player = spawn_player_from_level(level)

        self.assertEqual(player.x, 60.0)
        self.assertEqual(player.y, 80.0)

    def test_forward_motion_uses_legacy_speed(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.MOVE_FORWARD})

        self.assertAlmostEqual(player.x, 40.0)
        self.assertAlmostEqual(player.y, 42.0)

    def test_rotation_changes_by_nine_degrees(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.TURN_LEFT})
        self.assertEqual(player.angle, 9)

        apply_player_controls(player, level, {InputAction.TURN_RIGHT})
        self.assertEqual(player.angle, 0)

    def test_strafe_modifier_moves_without_rotation(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        apply_player_controls(
            player,
            level,
            {InputAction.STRAFE_MODIFIER, InputAction.TURN_LEFT},
        )

        self.assertEqual(player.angle, 0)
        self.assertAlmostEqual(player.x, 41.8)
        self.assertAlmostEqual(player.y, 40.0)

    def test_wall_collision_blocks_forward_motion(self) -> None:
        level = _build_level(walls={(2, 3)})
        player = spawn_player_from_level(level)

        apply_player_controls(player, level, {InputAction.MOVE_FORWARD})

        self.assertAlmostEqual(player.x, 40.0)
        self.assertAlmostEqual(player.y, 40.0)

    def test_weapon_cycle_skips_unowned_slots(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)
        player.grant_weapon(2)
        player.grant_weapon(4)

        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 2)
        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 4)
        cycle_weapon_slot(player)
        self.assertEqual(player.current_weapon, 0)

    def test_weapon_select_only_accepts_owned_slots(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        select_weapon_slot_if_owned(player, 5)
        self.assertEqual(player.current_weapon, 0)

        player.grant_weapon(5)
        select_weapon_slot_if_owned(player, 5)
        self.assertEqual(player.current_weapon, 5)

        select_weapon_slot_if_owned(player, 20)
        self.assertEqual(player.current_weapon, 5)

    def test_follow_camera_clamps_for_small_levels(self) -> None:
        level = _build_level(width=8, height=8)
        player = spawn_player_from_level(level)

        camera_x, camera_y = follow_player_camera(
            camera_x=50,
            camera_y=70,
            player=player,
            max_camera_x=0,
            max_camera_y=0,
        )
        self.assertEqual(camera_x, 0)
        self.assertEqual(camera_y, 0)

    def test_follow_camera_moves_toward_look_direction(self) -> None:
        level = _build_level(width=40, height=30, start=(12, 8))
        player = spawn_player_from_level(level)
        player.angle = 90

        start_camera_x = int(player.center_x) - 160
        start_camera_y = int(player.center_y) - 100
        next_camera_x, _ = follow_player_camera(
            camera_x=start_camera_x,
            camera_y=start_camera_y,
            player=player,
            max_camera_x=(level.level_x_size * 20) - 320,
            max_camera_y=(level.level_y_size * 20) - 200,
        )
        self.assertGreater(next_camera_x, start_camera_x)

    def test_aim_point_tracks_player_angle(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)

        player.angle = 0
        self.assertEqual(aim_point_from_player(player), (54, 64))

        player.angle = 90
        self.assertEqual(aim_point_from_player(player), (64, 54))

    def test_shoot_requires_weapon_reload_time(self) -> None:
        level = _build_level(height=12)
        player = spawn_player_from_level(level)

        for _ in range(10):
            apply_player_controls(player, level, {InputAction.SHOOT})
        self.assertEqual(player.shots_fired_total, 0)

        apply_player_controls(player, level, {InputAction.SHOOT})
        self.assertEqual(player.shots_fired_total, 1)
        self.assertEqual(player.load_count, 1)
        self.assertGreater(player.fire_animation_ticks, 0)

        pending = consume_pending_shots(player)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].weapon_slot, 0)
        self.assertEqual(len(consume_pending_shots(player)), 0)

    def test_autofire_respects_loading_cadence(self) -> None:
        level = _build_level(height=12)
        player = spawn_player_from_level(level)

        for _ in range(21):
            apply_player_controls(player, level, {InputAction.SHOOT})

        self.assertEqual(player.shots_fired_total, 2)

    def test_shot_impact_stops_before_wall(self) -> None:
        level = _build_level(height=12, walls={(2, 4)})
        player = spawn_player_from_level(level)

        for _ in range(11):
            apply_player_controls(player, level, {InputAction.SHOOT})

        self.assertEqual(player.shots_fired_total, 1)
        self.assertEqual(player.shot_effect_x, 54)
        self.assertLess(player.shot_effect_y, 80)
        self.assertGreater(player.shot_effect_y, 64)

        shot = consume_pending_shots(player)[0]
        self.assertEqual(shot.impact_x, player.shot_effect_x)
        self.assertEqual(shot.impact_y, player.shot_effect_y)

    def test_weapon_change_resets_reload_counter(self) -> None:
        level = _build_level()
        player = spawn_player_from_level(level)
        player.grant_weapon(1)
        player.load_count = 7

        apply_player_controls(player, level, (), cycle_weapon=True)
        self.assertEqual(player.current_weapon, 1)
        self.assertEqual(player.load_count, 1)

        player.grant_weapon(5)
        player.load_count = 6
        apply_player_controls(player, level, (), select_weapon_slot=5)
        self.assertEqual(player.current_weapon, 5)
        self.assertEqual(player.load_count, 1)

    def test_empty_weapon_switches_back_to_fist_when_shooting(self) -> None:
        level = _build_level(height=12)
        player = spawn_player_from_level(level)
        player.grant_weapon(1)
        player.current_weapon = 1
        player.load_count = 10

        apply_player_controls(player, level, {InputAction.SHOOT})

        self.assertEqual(player.current_weapon, 0)
        self.assertEqual(player.shots_fired_total, 0)
        self.assertEqual(len(consume_pending_shots(player)), 0)

    def test_weapon_with_ammo_consumes_one_round_per_shot(self) -> None:
        level = _build_level(height=12)
        player = spawn_player_from_level(level)
        player.grant_weapon(1)
        player.current_weapon = 1
        player.load_count = 10
        gained = grant_bullet_ammo(player, 0, 2)
        self.assertEqual(gained, 2)

        apply_player_controls(player, level, {InputAction.SHOOT})

        self.assertEqual(player.current_weapon, 1)
        self.assertEqual(player.shots_fired_total, 1)
        self.assertEqual(player.bullets[0], 1)
        self.assertEqual(len(consume_pending_shots(player)), 1)

    def test_current_weapon_ammo_snapshot_for_melee_weapon(self) -> None:
        player = PlayerState(x=40.0, y=40.0)

        ammo_type, ammo_units, ammo_capacity = current_weapon_ammo_snapshot(player)

        self.assertEqual(ammo_type, -1)
        self.assertEqual(ammo_units, 0)
        self.assertEqual(ammo_capacity, 0)

    def test_current_weapon_ammo_snapshot_for_gun_weapon(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        player.grant_weapon(1)
        player.current_weapon = 1
        player.bullets[0] = 350

        ammo_type, ammo_units, ammo_capacity = current_weapon_ammo_snapshot(player)

        self.assertEqual(ammo_type, 0)
        self.assertEqual(ammo_units, 300)
        self.assertEqual(ammo_capacity, 300)

    def test_bullet_ammo_capacities_snapshot_matches_legacy_caps(self) -> None:
        self.assertEqual(
            bullet_ammo_capacities_snapshot(),
            (300, 300, 300, 150, 125, 100, 100, 3000, 100),
        )

    def test_bullet_ammo_pools_snapshot_clamps_values(self) -> None:
        player = PlayerState(x=40.0, y=40.0)
        player.bullets = [350, -4, 7, 160, 0, 100, 99, 4500, 120]

        self.assertEqual(
            bullet_ammo_pools_snapshot(player),
            (300, 0, 7, 150, 0, 100, 99, 3000, 100),
        )

    def test_shop_buy_uses_legacy_cost_and_mul(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=20)

        gained = buy_bullet_ammo_from_shop(player, 7)

        self.assertEqual(bullet_shop_cost_for_type(7), 6)
        self.assertEqual(bullet_shop_units_for_type(7), 10)
        self.assertEqual(gained, 10)
        self.assertEqual(player.bullets[7], 10)
        self.assertEqual(player.cash, 14)

    def test_shop_buy_fails_without_cash_or_capacity(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=2)

        gained = buy_bullet_ammo_from_shop(player, 0)
        self.assertEqual(gained, 0)
        self.assertEqual(player.bullets[0], 0)
        self.assertEqual(player.cash, 2)

        player.cash = 20
        player.bullets[0] = 300
        gained = buy_bullet_ammo_from_shop(player, 0)
        self.assertEqual(gained, 0)
        self.assertEqual(player.bullets[0], 300)
        self.assertEqual(player.cash, 20)

    def test_shop_sell_grants_cash_and_handles_partial_stack(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=0)
        player.bullets[0] = 1

        sold = sell_bullet_ammo_to_shop(player, 0)
        self.assertEqual(sold, 1)
        self.assertEqual(player.bullets[0], 0)
        self.assertEqual(player.cash, 3)

        player.bullets[7] = 6
        sold = sell_bullet_ammo_to_shop(player, 7)
        self.assertEqual(sold, 6)
        self.assertEqual(player.bullets[7], 0)
        self.assertEqual(player.cash, 9)

    def test_weapon_shop_costs_match_legacy_values(self) -> None:
        self.assertEqual(
            tuple(weapon_shop_cost_for_slot(slot) for slot in range(1, 12)),
            (400, 1000, 2000, 4000, 4000, 6000, 6000, 6000, 1000, 3000, 1000),
        )

    def test_buy_weapon_requires_cash_and_unowned_slot(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=399)

        self.assertFalse(buy_weapon_from_shop(player, 1))
        self.assertFalse(player.weapons[1])

        player.cash = 400
        self.assertTrue(buy_weapon_from_shop(player, 1))
        self.assertTrue(player.weapons[1])
        self.assertEqual(player.cash, 0)

        self.assertFalse(buy_weapon_from_shop(player, 1))

    def test_sell_weapon_uses_sell_price_and_resets_equipped_weapon(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=10)
        player.grant_weapon(3)
        player.current_weapon = 3
        player.load_count = 7
        sell_prices = ShopSellPriceTable(
            weapon_slots=(11, 22, 33, 44, 55, 66, 77, 88, 99, 111, 222),
            shield_base=77,
            target_system=88,
        )

        self.assertTrue(sell_weapon_to_shop(player, 3, sell_prices))
        self.assertFalse(player.weapons[3])
        self.assertEqual(player.current_weapon, 0)
        self.assertEqual(player.load_count, 0)
        self.assertEqual(player.cash, 43)
        self.assertEqual(weapon_sell_price_for_slot(sell_prices, 3), 33)

    def test_generate_shop_sell_prices_is_deterministic_and_bounded(self) -> None:
        first = generate_shop_sell_prices(random_seed=42)
        second = generate_shop_sell_prices(random_seed=42)

        self.assertEqual(first, second)
        self.assertEqual(len(first.weapon_slots), 11)

        for weapon_slot, sell_price in enumerate(first.weapon_slots, start=1):
            max_price = int(0.8 * weapon_shop_cost_for_slot(weapon_slot))
            self.assertGreaterEqual(sell_price, 0)
            self.assertLessEqual(sell_price, max_price)

        self.assertGreaterEqual(first.shield_base, 0)
        self.assertLessEqual(first.shield_base, int(0.8 * 160))
        self.assertGreaterEqual(first.target_system, 0)
        self.assertLessEqual(first.target_system, int(0.8 * 500))

    def test_shield_buy_cost_scales_by_level(self) -> None:
        self.assertEqual(shield_shop_buy_cost_for_level(0), 160)
        self.assertEqual(shield_shop_buy_cost_for_level(1), 175)
        self.assertEqual(shield_shop_buy_cost_for_level(5), 235)

    def test_buy_shield_obeys_cash_and_level_cap(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=159)
        self.assertFalse(buy_shield_from_shop(player))
        self.assertEqual(player.shield, 0)

        player.cash = 160
        self.assertTrue(buy_shield_from_shop(player))
        self.assertEqual(player.shield, 1)
        self.assertEqual(player.cash, 0)

        player.shield = 30
        player.cash = 100000
        self.assertFalse(buy_shield_from_shop(player))
        self.assertEqual(player.shield, 30)

    def test_sell_shield_uses_legacy_formula(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=0, shield=5)
        sell_prices = ShopSellPriceTable(
            weapon_slots=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            shield_base=100,
            target_system=0,
        )

        self.assertTrue(sell_shield_to_shop(player, sell_prices))
        self.assertEqual(player.shield, 4)
        self.assertEqual(player.cash, 130)

    def test_target_system_shop_buy_and_sell(self) -> None:
        player = PlayerState(x=40.0, y=40.0, cash=499)
        sell_prices = ShopSellPriceTable(
            weapon_slots=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            shield_base=0,
            target_system=222,
        )

        self.assertFalse(buy_target_system_from_shop(player))
        player.cash = 500
        self.assertTrue(buy_target_system_from_shop(player))
        self.assertTrue(player.target_system_enabled)
        self.assertEqual(player.cash, 0)
        self.assertFalse(buy_target_system_from_shop(player))

        self.assertTrue(sell_target_system_to_shop(player, sell_prices))
        self.assertFalse(player.target_system_enabled)
        self.assertEqual(player.cash, 222)
        self.assertFalse(sell_target_system_to_shop(player, sell_prices))


if __name__ == "__main__":
    unittest.main()
