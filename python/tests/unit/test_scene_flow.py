from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.boot_scene import BootScene
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, InputAction
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.scenes import SceneManager
from ultimatetk.rendering import SCREEN_HEIGHT, SCREEN_WIDTH
from ultimatetk.systems.combat import CrateState, EnemyProjectile, EnemyState, PlayerExplosive
from ultimatetk.systems.player_control import (
    SHOP_ROW_AMMO,
    SHOP_ROW_OTHER,
    SHOP_ROW_WEAPONS,
    ShotEvent,
    bullet_capacity_units_for_type,
    grant_bullet_ammo,
)
from ultimatetk.ui.progression_scene import LevelCompleteScene, RunCompleteScene


class SceneFlowTests(unittest.TestCase):
    def _capture_hud_draw_state(
        self,
        gameplay_scene: object,
    ) -> tuple[list[dict[str, object]], list[tuple[str, int]]]:
        meter_calls: list[dict[str, object]] = []
        text_calls: list[tuple[str, int]] = []

        original_draw_meter = gameplay_scene._draw_meter  # type: ignore[attr-defined]
        original_draw_shop_text = gameplay_scene._draw_shop_text  # type: ignore[attr-defined]

        def capture_meter(
            pixels: bytearray,
            *,
            x: int,
            y: int,
            width: int,
            height: int,
            ratio: float,
            fill_color: int,
            border_color: int,
            background_color: int,
        ) -> None:
            del pixels
            meter_calls.append(
                {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "ratio": ratio,
                    "fill_color": fill_color,
                    "border_color": border_color,
                    "background_color": background_color,
                },
            )

        def capture_shop_text(
            pixels: bytearray,
            x: int,
            y: int,
            text: str,
            color: int,
        ) -> None:
            del pixels, x, y
            text_calls.append((text, color))

        gameplay_scene._draw_meter = capture_meter  # type: ignore[attr-defined]
        gameplay_scene._draw_shop_text = capture_shop_text  # type: ignore[attr-defined]

        try:
            gameplay_scene._draw_gameplay_hud(bytearray(SCREEN_WIDTH * SCREEN_HEIGHT))  # type: ignore[attr-defined]
        finally:
            gameplay_scene._draw_meter = original_draw_meter  # type: ignore[attr-defined]
            gameplay_scene._draw_shop_text = original_draw_shop_text  # type: ignore[attr-defined]

        return meter_calls, text_calls

    def _hud_meter_fill_color(
        self,
        meter_calls: list[dict[str, object]],
        *,
        x: int,
    ) -> int:
        for call in meter_calls:
            if call["x"] == x:
                return int(call["fill_color"])
        self.fail(f"missing HUD meter call for x={x}")

    def _hud_text_color_by_prefix(
        self,
        text_calls: list[tuple[str, int]],
        *,
        prefix: str,
    ) -> int:
        for text, color in text_calls:
            if text.startswith(prefix):
                return color
        self.fail(f"missing HUD text call for prefix={prefix!r}")

    def test_boot_to_menu_to_gameplay_autostart(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        self.assertEqual(manager.current_scene_name, "boot")
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

    def test_boot_to_menu_requires_manual_start_when_autostart_is_disabled(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        self.assertEqual(manager.current_scene_name, "boot")
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")

    def test_main_menu_quit_selection_sets_runtime_running_false(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")
        self.assertTrue(context.runtime.running)

        manager.handle_events((AppEvent.action_pressed(InputAction.MOVE_BACKWARD),))
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))

        self.assertEqual(manager.current_scene_name, "main_menu")
        self.assertFalse(context.runtime.running)

    def test_gameplay_death_returns_to_main_menu_without_autostart_loop(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.dead = True
        player.health = 0.0

        for _ in range(120):
            manager.update(0.025)
            if manager.current_scene_name == "main_menu":
                break

        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

    def test_gameplay_death_returns_to_menu_and_manual_start_reenters_gameplay(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.dead = True
        player.health = 0.0

        for _ in range(120):
            manager.update(0.025)
            if manager.current_scene_name == "main_menu":
                break

        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")

    def test_level_completion_advances_session_index_and_reloads_gameplay_when_progression_enabled(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")
        self.assertEqual(context.session.level_index, 0)

        original_scene = manager._current_scene  # type: ignore[attr-defined]
        enemies = getattr(original_scene, "_enemies", None)
        if enemies is None:
            self.skipTest("gameplay scene did not initialize enemies")

        enemies.clear()
        manager.update(0.025)

        self.assertEqual(manager.current_scene_name, "level_complete")
        self.assertEqual(context.runtime.progression_event, "level_complete")
        self.assertEqual(context.runtime.progression_from_level_index, 0)
        self.assertEqual(context.runtime.progression_to_level_index, 1)
        self.assertTrue(context.runtime.progression_has_next_level)
        self.assertGreater(context.runtime.progression_ticks_remaining, 0)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(context.runtime.progression_ticks_remaining, 0)
        manager.update(0.025)

        self.assertEqual(manager.current_scene_name, "gameplay")
        self.assertIsNot(manager._current_scene, original_scene)  # type: ignore[attr-defined]
        self.assertEqual(context.session.level_index, 1)

    def test_level_complete_scene_uses_phase7_hold_ticks(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        scene = LevelCompleteScene(from_level_index=0, to_level_index=1)

        scene.on_enter(context)

        self.assertEqual(context.runtime.progression_ticks_remaining, 20)

    def test_level_completion_fallback_returns_to_menu_when_next_level_is_missing(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        context.session.level_index = 9
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        enemies = getattr(gameplay_scene, "_enemies", None)
        if enemies is None:
            self.skipTest("gameplay scene did not initialize enemies")

        enemies.clear()
        manager.update(0.025)

        self.assertEqual(manager.current_scene_name, "run_complete")
        self.assertEqual(context.runtime.progression_event, "run_complete")
        self.assertEqual(context.runtime.progression_from_level_index, 9)
        self.assertEqual(context.runtime.progression_to_level_index, 0)
        self.assertFalse(context.runtime.progression_has_next_level)
        self.assertGreater(context.runtime.progression_ticks_remaining, 0)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(context.runtime.progression_ticks_remaining, 0)
        manager.update(0.025)

        self.assertEqual(manager.current_scene_name, "main_menu")
        self.assertEqual(context.session.level_index, 0)

    def test_run_complete_scene_uses_phase7_hold_ticks(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        scene = RunCompleteScene(completed_level_index=9)

        scene.on_enter(context)

        self.assertEqual(context.runtime.progression_ticks_remaining, 30)

    def test_gameplay_death_does_not_advance_session_index_when_progression_enabled(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.dead = True
        player.health = 0.0

        for _ in range(120):
            manager.update(0.025)
            if manager.current_scene_name == "main_menu":
                break

        self.assertEqual(manager.current_scene_name, "main_menu")
        self.assertEqual(context.session.level_index, 0)

    def test_gameplay_action_idle_camera_catchup_is_faster_than_idle(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        if player is None or enemies is None or enemy_projectiles is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        enemy_projectiles.clear()

        player.angle = 90
        player.walking = False
        player.strafing = False
        player.turning = False
        player.moving_forward = False
        player.moving_backward = False

        target_camera_x = int(player.center_x + 25.0) - 160
        start_camera_x = target_camera_x - 14
        start_camera_y = int(player.center_y) - 100

        gameplay_scene._camera_x = start_camera_x  # type: ignore[attr-defined]
        gameplay_scene._camera_y = start_camera_y  # type: ignore[attr-defined]
        player.shoot_hold_count = 0
        player.fire_animation_ticks = 0
        manager.update(0.025)
        idle_camera_x = gameplay_scene._camera_x  # type: ignore[attr-defined]

        gameplay_scene._camera_x = start_camera_x  # type: ignore[attr-defined]
        gameplay_scene._camera_y = start_camera_y  # type: ignore[attr-defined]
        player.shoot_hold_count = 0
        player.fire_animation_ticks = 2
        manager.update(0.025)
        action_camera_x = gameplay_scene._camera_x  # type: ignore[attr-defined]

        self.assertGreater(action_camera_x, idle_camera_x)
        self.assertGreaterEqual(action_camera_x - idle_camera_x, 2)

    def test_manual_menu_progression_loop_returns_to_menu_and_restarts_from_level_one(self) -> None:
        config = RuntimeConfig(autostart_gameplay=False)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        context.session.level_index = 8
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")
        self.assertEqual(context.session.level_index, 8)

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        enemies = getattr(gameplay_scene, "_enemies", None)
        if enemies is None:
            self.skipTest("gameplay scene did not initialize enemies")
        enemies.clear()

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "level_complete")
        self.assertEqual(context.runtime.progression_event, "level_complete")
        self.assertEqual(context.runtime.progression_from_level_index, 8)
        self.assertEqual(context.runtime.progression_to_level_index, 9)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")
        self.assertEqual(context.session.level_index, 9)

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        enemies = getattr(gameplay_scene, "_enemies", None)
        if enemies is None:
            self.skipTest("gameplay scene did not initialize enemies")
        enemies.clear()

        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "run_complete")
        self.assertEqual(context.runtime.progression_event, "run_complete")
        self.assertEqual(context.runtime.progression_from_level_index, 9)
        self.assertEqual(context.runtime.progression_to_level_index, 0)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "main_menu")
        self.assertEqual(context.session.level_index, 0)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        self.assertEqual(manager.current_scene_name, "gameplay")
        self.assertEqual(context.session.level_index, 0)

    def test_gameplay_death_clears_active_projectiles_and_explosives_same_tick(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemy_projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        player_explosives = getattr(gameplay_scene, "_player_explosives", None)
        if player is None or enemy_projectiles is None or player_explosives is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemy_projectiles.clear()
        player_explosives.clear()
        enemy_projectiles.append(
            EnemyProjectile(
                owner_enemy_id=0,
                weapon_slot=1,
                x=220.0,
                y=220.0,
                vx=0.0,
                vy=1.0,
                speed=0.0,
                damage=5.0,
                remaining_ticks=20,
                radius=1,
                splash_radius=0,
            ),
        )
        player_explosives.append(
            PlayerExplosive(
                kind="c4",
                x=120.0,
                y=120.0,
                angle=0,
                fuse_ticks=1,
                arming_ticks=0,
                radius=80,
                damage=30.0,
                falloff_exponent=1.05,
            ),
        )
        gameplay_scene._player_explosive_detonations = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_hits_on_player = 0  # type: ignore[attr-defined]
        gameplay_scene._enemy_damage_to_player = 0.0  # type: ignore[attr-defined]

        player.dead = True
        player.health = 0.0

        manager.update(0.025)

        self.assertEqual(len(enemy_projectiles), 0)
        self.assertEqual(len(player_explosives), 0)
        self.assertEqual(context.runtime.enemy_projectiles_active, 0)
        self.assertEqual(context.runtime.player_explosives_active, 0)
        self.assertEqual(context.runtime.player_explosive_detonations_total, 0)
        self.assertEqual(context.runtime.enemy_hits_total, 0)
        self.assertEqual(context.runtime.enemy_damage_to_player_total, 0.0)
        self.assertTrue(context.runtime.game_over_active)
        self.assertTrue(context.runtime.player_dead)

    def test_gameplay_collects_touching_crate_and_updates_runtime_counter(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        crates = getattr(gameplay_scene, "_crates", None)
        if player is None or crates is None:
            self.skipTest("gameplay scene did not initialize crates/player")

        crates.clear()
        crates.append(
            CrateState(
                crate_id=0,
                type1=1,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )

        manager.update(0.025)

        self.assertEqual(context.runtime.crates_collected_by_player, 1)
        self.assertEqual(context.runtime.crates_alive, 0)

    def test_gameplay_collect_beats_same_tick_destroy_for_same_crate(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        if player is None or enemies is None or crates is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        crates.clear()
        player.health = 70.0
        crates.append(
            CrateState(
                crate_id=0,
                type1=2,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        player.pending_shots.append(
            ShotEvent(
                origin_x=player.center_x,
                origin_y=player.center_y + 10.0,
                angle=180,
                max_distance=34,
                weapon_slot=7,
                impact_x=int(player.center_x),
                impact_y=int(player.center_y - 24.0),
            ),
        )
        gameplay_scene._crates_collected_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]

        manager.update(0.025)

        self.assertEqual(context.runtime.crates_collected_by_player, 1)
        self.assertEqual(context.runtime.crates_destroyed_by_player, 0)
        self.assertEqual(context.runtime.crates_alive, 0)
        self.assertEqual(context.runtime.player_health, 100)

    def test_gameplay_full_health_energy_crate_not_collected_then_destroyed(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        if player is None or enemies is None or crates is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        crates.clear()
        player.health = 100.0
        crates.append(
            CrateState(
                crate_id=0,
                type1=2,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        player.pending_shots.append(
            ShotEvent(
                origin_x=player.center_x,
                origin_y=player.center_y + 10.0,
                angle=180,
                max_distance=34,
                weapon_slot=7,
                impact_x=int(player.center_x),
                impact_y=int(player.center_y - 24.0),
            ),
        )
        gameplay_scene._crates_collected_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]

        manager.update(0.025)

        self.assertEqual(context.runtime.crates_collected_by_player, 0)
        self.assertEqual(context.runtime.crates_destroyed_by_player, 1)
        self.assertEqual(context.runtime.crates_alive, 0)
        self.assertEqual(context.runtime.player_health, 100)

    def test_gameplay_mixed_crate_collect_and_destroy_counters_are_consistent(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        if player is None or enemies is None or crates is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        crates.clear()
        player.health = 70.0
        player.weapons[1] = False
        crates.append(
            CrateState(
                crate_id=0,
                type1=2,
                type2=0,
                x=player.x + 6.0,
                y=player.y + 6.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        crates.append(
            CrateState(
                crate_id=1,
                type1=0,
                type2=0,
                x=48.0,
                y=84.0,
                health=12.0,
                max_health=12.0,
            ),
        )
        player.pending_shots.append(
            ShotEvent(
                origin_x=54.0,
                origin_y=64.0,
                angle=0,
                max_distance=170,
                weapon_slot=7,
                impact_x=54,
                impact_y=130,
            ),
        )
        gameplay_scene._crates_collected_by_player = 0  # type: ignore[attr-defined]
        gameplay_scene._crates_destroyed_by_player = 0  # type: ignore[attr-defined]

        manager.update(0.025)

        self.assertEqual(context.runtime.crates_collected_by_player, 1)
        self.assertEqual(context.runtime.crates_destroyed_by_player, 1)
        self.assertEqual(context.runtime.crates_alive, 0)
        self.assertEqual(context.runtime.player_health, 100)
        self.assertFalse(player.weapons[1])

    def test_gameplay_runtime_reports_current_weapon_ammo_snapshot(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.grant_weapon(1)
        player.current_weapon = 1
        player.cash = 321
        player.shield = 4
        player.target_system_enabled = True
        gained = grant_bullet_ammo(player, 0, 37)
        self.assertEqual(gained, 37)
        gained = grant_bullet_ammo(player, 7, 4000)
        self.assertEqual(gained, 3000)

        manager.update(0.025)
        self.assertEqual(context.runtime.player_current_ammo_type_index, 0)
        self.assertEqual(context.runtime.player_current_ammo_units, 37)
        self.assertEqual(context.runtime.player_current_ammo_capacity, 300)
        self.assertEqual(context.runtime.player_cash, 321)
        self.assertEqual(context.runtime.player_shield, 4)
        self.assertTrue(context.runtime.player_target_system_enabled)
        self.assertEqual(
            context.runtime.player_ammo_pools,
            (37, 0, 0, 0, 0, 0, 0, 3000, 0),
        )
        self.assertEqual(
            context.runtime.player_ammo_capacities,
            (300, 300, 300, 150, 125, 100, 100, 3000, 100),
        )

        player.current_weapon = 0
        manager.update(0.025)
        self.assertEqual(context.runtime.player_current_ammo_type_index, -1)
        self.assertEqual(context.runtime.player_current_ammo_units, 0)
        self.assertEqual(context.runtime.player_current_ammo_capacity, 0)
        self.assertEqual(
            context.runtime.player_ammo_pools,
            (37, 0, 0, 0, 0, 0, 0, 3000, 0),
        )

    def test_gameplay_shop_toggle_buy_and_sell_updates_runtime(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.cash = 500

        manager.handle_events((AppEvent.action_pressed(InputAction.TOGGLE_SHOP),))
        manager.update(0.025)
        self.assertTrue(context.runtime.shop_active)
        self.assertEqual(context.runtime.shop_selection_row, 0)
        self.assertEqual(context.runtime.shop_selection_column, 0)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        self.assertTrue(player.weapons[1])
        self.assertEqual(context.runtime.player_cash, 100)
        self.assertEqual(context.runtime.shop_last_action, "buy")
        self.assertEqual(context.runtime.shop_last_category, "weapon")
        self.assertTrue(context.runtime.shop_last_success)
        self.assertEqual(context.runtime.shop_last_cash_delta, -400)
        self.assertEqual(context.runtime.shop_last_reason, "")

        sell_price = gameplay_scene._shop_sell_prices.weapon_slots[0]
        manager.handle_events((AppEvent.action_pressed(InputAction.NEXT_WEAPON),))
        manager.update(0.025)
        self.assertFalse(player.weapons[1])
        self.assertEqual(context.runtime.player_cash, 100 + sell_price)
        self.assertEqual(context.runtime.shop_last_action, "sell")
        self.assertEqual(context.runtime.shop_last_category, "weapon")
        self.assertTrue(context.runtime.shop_last_success)
        self.assertEqual(context.runtime.shop_last_cash_delta, sell_price)
        self.assertEqual(context.runtime.shop_last_reason, "")

        manager.handle_events((AppEvent.action_pressed(InputAction.TOGGLE_SHOP),))
        manager.update(0.025)
        self.assertFalse(context.runtime.shop_active)

    def test_gameplay_shop_navigation_clamps_and_reports_failed_buy(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        manager.handle_events((AppEvent.action_pressed(InputAction.TOGGLE_SHOP),))
        manager.update(0.025)
        self.assertTrue(context.runtime.shop_active)

        for _ in range(20):
            manager.handle_events((AppEvent.action_pressed(InputAction.TURN_RIGHT),))
            manager.update(0.025)
        self.assertEqual(context.runtime.shop_selection_row, 0)
        self.assertEqual(context.runtime.shop_selection_column, 10)

        manager.handle_events((AppEvent.action_pressed(InputAction.MOVE_BACKWARD),))
        manager.update(0.025)
        self.assertEqual(context.runtime.shop_selection_row, 1)
        self.assertEqual(context.runtime.shop_selection_column, 8)

        manager.handle_events((AppEvent.action_pressed(InputAction.MOVE_BACKWARD),))
        manager.update(0.025)
        self.assertEqual(context.runtime.shop_selection_row, 2)
        self.assertEqual(context.runtime.shop_selection_column, 1)

        player.cash = 0
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        self.assertEqual(context.runtime.shop_last_action, "buy")
        self.assertEqual(context.runtime.shop_last_category, "target")
        self.assertFalse(context.runtime.shop_last_success)
        self.assertEqual(context.runtime.shop_last_units, 0)
        self.assertEqual(context.runtime.shop_last_cash_delta, 0)
        self.assertEqual(context.runtime.shop_last_reason, "NO CASH")

    def test_gameplay_shop_cell_state_reports_owned_full_no_cash_and_buy(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.grant_weapon(1)
        player.cash = 0
        player.bullets[0] = 0
        self.assertEqual(gameplay_scene._shop_cell_state(SHOP_ROW_WEAPONS, 0), "owned")
        self.assertEqual(gameplay_scene._shop_cell_state(SHOP_ROW_AMMO, 0), "no_cash")

        player.bullets[0] = bullet_capacity_units_for_type(0)
        self.assertEqual(gameplay_scene._shop_cell_state(SHOP_ROW_AMMO, 0), "full")

        player.bullets[0] = 0
        player.cash = 9999
        self.assertEqual(gameplay_scene._shop_cell_state(SHOP_ROW_AMMO, 0), "buy")

    def test_gameplay_shop_cell_visual_colors_follow_cell_state(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.grant_weapon(1)
        owned_colors = gameplay_scene._shop_cell_visual_colors(
            SHOP_ROW_WEAPONS,
            0,
            selected=False,
            selected_pulse=False,
        )
        self.assertEqual(owned_colors[2], gameplay_scene._SHOP_MUTED_COLOR)
        self.assertEqual(owned_colors[3], gameplay_scene._SHOP_MUTED_COLOR)
        self.assertEqual(owned_colors[5], gameplay_scene._SHOP_SUCCESS_COLOR)

        player.cash = 0
        player.bullets[0] = 0
        gameplay_scene._shop_row = SHOP_ROW_AMMO
        gameplay_scene._shop_column = 0
        no_cash_colors = gameplay_scene._shop_cell_visual_colors(
            SHOP_ROW_AMMO,
            0,
            selected=True,
            selected_pulse=True,
        )
        self.assertEqual(no_cash_colors[2], gameplay_scene._SHOP_ERROR_COLOR)
        self.assertEqual(no_cash_colors[3], gameplay_scene._SHOP_ERROR_COLOR)
        self.assertEqual(no_cash_colors[5], gameplay_scene._SHOP_ERROR_COLOR)
        self.assertEqual(gameplay_scene._shop_selection_state_color(), gameplay_scene._SHOP_ERROR_COLOR)

        player.cash = 9999
        buy_colors = gameplay_scene._shop_cell_visual_colors(
            SHOP_ROW_AMMO,
            0,
            selected=True,
            selected_pulse=True,
        )
        self.assertEqual(buy_colors[5], gameplay_scene._SHOP_VALUE_COLOR)
        self.assertEqual(gameplay_scene._shop_selection_state_color(), gameplay_scene._SHOP_VALUE_COLOR)

    def test_gameplay_shop_icon_catalog_covers_all_slots_with_distinct_silhouettes(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        icon_bitmaps = gameplay_scene._SHOP_ICON_BITMAPS
        weapon_kinds = [
            gameplay_scene._shop_cell_icon_kind(SHOP_ROW_WEAPONS, column)
            for column in range(11)
        ]
        ammo_kinds = [
            gameplay_scene._shop_cell_icon_kind(SHOP_ROW_AMMO, column)
            for column in range(9)
        ]
        other_kinds = [
            gameplay_scene._shop_cell_icon_kind(SHOP_ROW_OTHER, 0),
            gameplay_scene._shop_cell_icon_kind(SHOP_ROW_OTHER, 1),
        ]

        for kind in weapon_kinds + ammo_kinds + other_kinds:
            self.assertIn(kind, icon_bitmaps)
            pattern = icon_bitmaps[kind]
            self.assertEqual(len(pattern), 7)
            self.assertTrue(all(len(row) == 7 for row in pattern))
            self.assertGreaterEqual(sum(row.count("#") for row in pattern), 8)

        self.assertEqual(
            len({icon_bitmaps[kind] for kind in weapon_kinds}),
            len(weapon_kinds),
        )
        self.assertEqual(
            len({icon_bitmaps[kind] for kind in ammo_kinds}),
            len(ammo_kinds),
        )

    def test_gameplay_shop_cell_text_alignment_uses_two_character_slots(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.bullets[0] = 1
        player.bullets[7] = 40
        player.shield = 3

        self.assertEqual(gameplay_scene._shop_cell_counter_text(SHOP_ROW_AMMO, 0), "01")
        self.assertEqual(gameplay_scene._shop_cell_counter_text(SHOP_ROW_AMMO, 7), "04")
        self.assertEqual(gameplay_scene._shop_cell_counter_text(SHOP_ROW_OTHER, 0), "03")

        self.assertEqual(gameplay_scene._shop_cell_aligned_text("7", pad_numeric=True), "07")
        self.assertEqual(gameplay_scene._shop_cell_aligned_text("x"), "X ")

        cell_x = 52
        weapon_label = gameplay_scene._shop_cell_aligned_text(
            gameplay_scene._shop_cell_label_text(SHOP_ROW_WEAPONS, 0),
        )
        ammo_label = gameplay_scene._shop_cell_aligned_text(
            gameplay_scene._shop_cell_label_text(SHOP_ROW_AMMO, 0),
        )
        self.assertEqual(len(weapon_label), 2)
        self.assertEqual(len(ammo_label), 2)
        self.assertEqual(gameplay_scene._shop_cell_text_x(cell_x, weapon_label), cell_x)
        self.assertEqual(gameplay_scene._shop_cell_text_x(cell_x, ammo_label), cell_x)
        self.assertEqual(
            gameplay_scene._shop_cell_text_x(cell_x, gameplay_scene._shop_cell_counter_text(SHOP_ROW_AMMO, 0)),
            cell_x,
        )

    def test_gameplay_shop_overlay_changes_render_digest(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.cash = 1234
        gameplay_scene._shop_row = 1
        gameplay_scene._shop_column = 7

        gameplay_scene._shop_active = False
        manager.render(0.0)
        digest_without_shop = context.runtime.last_render_digest

        gameplay_scene._shop_active = True
        manager.render(0.0)
        digest_with_shop = context.runtime.last_render_digest

        self.assertNotEqual(digest_without_shop, digest_with_shop)

    def test_gameplay_hud_overlay_changes_render_digest_with_runtime_values(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        ui_font = getattr(gameplay_scene, "_ui_font", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")
        if ui_font is None:
            self.skipTest("gameplay scene did not load UI font")

        gameplay_scene._shop_active = False
        manager.render(0.0)
        digest_before = context.runtime.last_render_digest

        player.cash = 1337
        player.shield = 7
        player.health = 31.0
        player.grant_weapon(1)
        player.current_weapon = 1
        gained = grant_bullet_ammo(player, 0, 11)
        self.assertEqual(gained, 11)

        manager.render(0.0)
        digest_after = context.runtime.last_render_digest

        self.assertNotEqual(digest_before, digest_after)

    def test_gameplay_hud_warning_transitions_cover_hp_ammo_c4_and_mines(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.grant_weapon(1)
        player.current_weapon = 1
        player.load_count = player.current_weapon_profile.loading_time
        player.health = 31.0
        player.bullets[0] = 61
        gameplay_scene._player_explosives = []

        meter_calls, text_calls = self._capture_hud_draw_state(gameplay_scene)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=4), gameplay_scene._HUD_OK_COLOR)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=80), gameplay_scene._HUD_OK_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="HP "), gameplay_scene._HUD_OK_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="AM "), gameplay_scene._HUD_OK_COLOR)

        player.health = 30.0
        player.bullets[0] = 60
        meter_calls, text_calls = self._capture_hud_draw_state(gameplay_scene)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=4), gameplay_scene._HUD_WARN_COLOR)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=80), gameplay_scene._HUD_WARN_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="HP "), gameplay_scene._HUD_WARN_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="AM "), gameplay_scene._HUD_WARN_COLOR)

        player.health = 31.0
        player.bullets[0] = 61
        unarmed_mine = PlayerExplosive(
            kind="mine",
            x=player.x,
            y=player.y,
            angle=0,
            fuse_ticks=180,
            arming_ticks=3,
            radius=26,
            damage=120.0,
            trigger_radius=20,
        )
        cool_c4 = PlayerExplosive(
            kind="c4",
            x=player.x + 8.0,
            y=player.y,
            angle=0,
            fuse_ticks=30,
            arming_ticks=0,
            radius=28,
            damage=100.0,
        )
        gameplay_scene._player_explosives = [unarmed_mine, cool_c4]

        meter_calls, text_calls = self._capture_hud_draw_state(gameplay_scene)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=216), gameplay_scene._HUD_TEXT_COLOR)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=268), gameplay_scene._HUD_TEXT_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="M "), gameplay_scene._HUD_TEXT_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="C4 "), gameplay_scene._HUD_TEXT_COLOR)

        unarmed_mine.arming_ticks = 0
        cool_c4.fuse_ticks = gameplay_scene._C4_HOT_FUSE_TICKS
        meter_calls, text_calls = self._capture_hud_draw_state(gameplay_scene)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=216), gameplay_scene._HUD_OK_COLOR)
        self.assertEqual(self._hud_meter_fill_color(meter_calls, x=268), gameplay_scene._HUD_WARN_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="M "), gameplay_scene._HUD_OK_COLOR)
        self.assertEqual(self._hud_text_color_by_prefix(text_calls, prefix="C4 "), gameplay_scene._HUD_WARN_COLOR)

    def test_gameplay_player_mine_shot_deploys_and_detonates(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        explosives = getattr(gameplay_scene, "_player_explosives", None)
        if player is None or enemies is None or explosives is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=80.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
        )
        enemies.append(enemy)

        player.pending_shots.append(
            ShotEvent(
                origin_x=enemy.center_x,
                origin_y=enemy.center_y,
                angle=0,
                max_distance=34,
                weapon_slot=11,
                impact_x=int(enemy.center_x),
                impact_y=int(enemy.center_y),
            ),
        )

        manager.update(0.025)
        self.assertEqual(len(explosives), 1)
        self.assertEqual(context.runtime.player_explosives_active, 1)
        self.assertEqual(context.runtime.player_mines_active, 1)
        self.assertEqual(context.runtime.player_mines_armed, 0)
        self.assertEqual(context.runtime.player_c4_active, 0)
        self.assertEqual(context.runtime.player_c4_hot, 0)
        explosives[0].arming_ticks = 1

        manager.update(0.025)

        self.assertEqual(len(explosives), 0)
        self.assertEqual(context.runtime.player_explosives_active, 0)
        self.assertEqual(context.runtime.player_mines_active, 0)
        self.assertEqual(context.runtime.player_mines_armed, 0)
        self.assertEqual(context.runtime.player_c4_active, 0)
        self.assertEqual(context.runtime.player_c4_hot, 0)
        self.assertGreaterEqual(context.runtime.player_explosive_detonations_total, 1)
        self.assertFalse(enemy.alive)
        self.assertGreaterEqual(context.runtime.player_hits_total, 1)
        self.assertGreaterEqual(context.runtime.enemies_killed_by_player, 1)

    def test_gameplay_c4_second_shot_remote_triggers_existing_charge(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        explosives = getattr(gameplay_scene, "_player_explosives", None)
        if player is None or enemies is None or explosives is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        enemy = EnemyState(
            enemy_id=0,
            type_index=0,
            x=80.0,
            y=80.0,
            health=18.0,
            max_health=18.0,
            angle=180,
            target_angle=180,
        )
        enemies.append(enemy)

        player.pending_shots.append(
            ShotEvent(
                origin_x=enemy.center_x,
                origin_y=enemy.center_y,
                angle=0,
                max_distance=34,
                weapon_slot=9,
                impact_x=int(enemy.center_x),
                impact_y=int(enemy.center_y),
            ),
        )

        manager.update(0.025)
        self.assertEqual(len(explosives), 1)
        self.assertEqual(context.runtime.player_explosives_active, 1)
        self.assertEqual(context.runtime.player_c4_active, 1)
        self.assertEqual(context.runtime.player_c4_hot, 0)

        explosives[0].fuse_ticks = 12
        manager.update(0.025)
        self.assertEqual(context.runtime.player_c4_active, 1)
        self.assertEqual(context.runtime.player_c4_hot, 1)

        player.pending_shots.append(
            ShotEvent(
                origin_x=enemy.center_x,
                origin_y=enemy.center_y,
                angle=0,
                max_distance=34,
                weapon_slot=9,
                impact_x=int(enemy.center_x),
                impact_y=int(enemy.center_y),
            ),
        )

        manager.update(0.025)

        self.assertEqual(len(explosives), 0)
        self.assertEqual(context.runtime.player_explosives_active, 0)
        self.assertEqual(context.runtime.player_c4_active, 0)
        self.assertEqual(context.runtime.player_c4_hot, 0)
        self.assertGreaterEqual(context.runtime.player_explosive_detonations_total, 1)
        self.assertFalse(enemy.alive)

    def test_gameplay_c4_remote_trigger_does_not_consume_extra_c4_ammo(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        explosives = getattr(gameplay_scene, "_player_explosives", None)
        if player is None or enemies is None or explosives is None:
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        player.grant_weapon(9)
        player.current_weapon = 9
        player.load_count = player.current_weapon_profile.loading_time
        gained = grant_bullet_ammo(player, 6, 2)
        self.assertEqual(gained, 2)

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        manager.handle_events((AppEvent.action_released(InputAction.SHOOT),))
        manager.update(0.025)

        self.assertEqual(len(explosives), 1)
        self.assertEqual(player.bullets[6], 1)
        self.assertEqual(context.runtime.player_shots_fired_total, 1)
        self.assertEqual(context.runtime.player_current_ammo_type_index, 6)
        self.assertEqual(context.runtime.player_current_ammo_units, 1)
        self.assertEqual(context.runtime.player_current_ammo_capacity, bullet_capacity_units_for_type(6))
        self.assertEqual(context.runtime.player_weapon_slot, 9)

        player.load_count = player.current_weapon_profile.loading_time
        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        manager.handle_events((AppEvent.action_released(InputAction.SHOOT),))
        manager.update(0.025)

        self.assertEqual(len(explosives), 0)
        self.assertEqual(player.bullets[6], 1)
        self.assertEqual(context.runtime.player_shots_fired_total, 2)
        self.assertEqual(context.runtime.player_current_ammo_type_index, 6)
        self.assertEqual(context.runtime.player_current_ammo_units, 1)
        self.assertEqual(context.runtime.player_current_ammo_capacity, bullet_capacity_units_for_type(6))
        self.assertEqual(context.runtime.player_weapon_slot, 9)
        self.assertGreaterEqual(context.runtime.player_explosive_detonations_total, 1)

    def test_gameplay_empty_weapon_fallback_keeps_runtime_shot_and_ammo_state_consistent(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        if player is None:
            self.skipTest("gameplay scene did not initialize player")

        player.grant_weapon(1)
        player.current_weapon = 1
        player.load_count = player.current_weapon_profile.loading_time
        player.shots_fired_total = 0
        player.bullets[0] = 0

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        manager.handle_events((AppEvent.action_released(InputAction.SHOOT),))
        manager.update(0.025)

        self.assertEqual(player.current_weapon, 0)
        self.assertEqual(player.shots_fired_total, 0)
        self.assertEqual(player.bullets[0], 0)
        self.assertEqual(context.runtime.player_weapon_slot, 0)
        self.assertEqual(context.runtime.player_shots_fired_total, 0)
        self.assertEqual(context.runtime.player_current_ammo_type_index, -1)
        self.assertEqual(context.runtime.player_current_ammo_units, 0)
        self.assertEqual(context.runtime.player_current_ammo_capacity, 0)

    def test_gameplay_runtime_combat_telemetry_totals_are_monotonic_and_active_counts_match_state(self) -> None:
        config = RuntimeConfig(autostart_gameplay=True)
        paths = GamePaths(
            python_root=PROJECT_ROOT,
            game_data_root=PROJECT_ROOT / "game_data",
            runs_root=PROJECT_ROOT / "runs",
        )
        context = GameContext(config=config, paths=paths)
        manager = SceneManager(BootScene(), context)

        manager.update(0.025)
        manager.update(0.025)
        self.assertEqual(manager.current_scene_name, "gameplay")

        gameplay_scene = manager._current_scene  # type: ignore[attr-defined]
        player = getattr(gameplay_scene, "_player", None)
        explosives = getattr(gameplay_scene, "_player_explosives", None)
        projectiles = getattr(gameplay_scene, "_enemy_projectiles", None)
        enemies = getattr(gameplay_scene, "_enemies", None)
        crates = getattr(gameplay_scene, "_crates", None)
        if (
            player is None
            or explosives is None
            or projectiles is None
            or enemies is None
            or crates is None
        ):
            self.skipTest("gameplay scene did not initialize combat state")

        enemies.clear()
        crates.clear()
        projectiles.clear()
        explosives.clear()

        player.health = 100.0
        player.dead = False
        player.grant_weapon(11)
        player.current_weapon = 11
        player.load_count = player.current_weapon_profile.loading_time
        gained = grant_bullet_ammo(player, 8, 1)
        self.assertEqual(gained, 1)

        snapshots: list[tuple[int, int, int, float, int, int, float, int]] = []

        manager.handle_events((AppEvent.action_pressed(InputAction.SHOOT),))
        manager.update(0.025)
        manager.handle_events((AppEvent.action_released(InputAction.SHOOT),))

        snapshots.append(
            (
                context.runtime.player_shots_fired_total,
                context.runtime.player_hits_total,
                context.runtime.player_hits_taken_total,
                context.runtime.player_damage_taken_total,
                context.runtime.enemy_hits_total,
                context.runtime.enemy_shots_fired_total,
                context.runtime.enemy_damage_to_player_total,
                context.runtime.player_explosive_detonations_total,
            ),
        )
        self.assertEqual(context.runtime.player_explosives_active, len(explosives))
        self.assertEqual(context.runtime.enemy_projectiles_active, len(projectiles))

        self.assertEqual(len(explosives), 1)
        explosives[0].arming_ticks = 1
        explosives[0].fuse_ticks = 1
        projectiles.append(
            EnemyProjectile(
                owner_enemy_id=999,
                weapon_slot=1,
                x=player.center_x,
                y=player.center_y,
                vx=0.0,
                vy=0.0,
                speed=0.0,
                damage=5.0,
                remaining_ticks=5,
                radius=1,
                splash_radius=0,
            ),
        )

        manager.update(0.025)
        snapshots.append(
            (
                context.runtime.player_shots_fired_total,
                context.runtime.player_hits_total,
                context.runtime.player_hits_taken_total,
                context.runtime.player_damage_taken_total,
                context.runtime.enemy_hits_total,
                context.runtime.enemy_shots_fired_total,
                context.runtime.enemy_damage_to_player_total,
                context.runtime.player_explosive_detonations_total,
            ),
        )
        self.assertEqual(context.runtime.player_explosives_active, len(explosives))
        self.assertEqual(context.runtime.enemy_projectiles_active, len(projectiles))
        self.assertLessEqual(context.runtime.enemy_hits_total, context.runtime.player_hits_taken_total)
        self.assertLessEqual(context.runtime.enemy_damage_to_player_total, context.runtime.player_damage_taken_total)

        manager.update(0.025)
        snapshots.append(
            (
                context.runtime.player_shots_fired_total,
                context.runtime.player_hits_total,
                context.runtime.player_hits_taken_total,
                context.runtime.player_damage_taken_total,
                context.runtime.enemy_hits_total,
                context.runtime.enemy_shots_fired_total,
                context.runtime.enemy_damage_to_player_total,
                context.runtime.player_explosive_detonations_total,
            ),
        )
        self.assertEqual(context.runtime.player_explosives_active, len(explosives))
        self.assertEqual(context.runtime.enemy_projectiles_active, len(projectiles))

        for previous, current in zip(snapshots, snapshots[1:]):
            for index, value in enumerate(previous):
                self.assertGreaterEqual(current[index], value)


if __name__ == "__main__":
    unittest.main()
