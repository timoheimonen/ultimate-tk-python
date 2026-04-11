from __future__ import annotations

import sys
from pathlib import Path
import unittest

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if np is not None:
    from ultimatetk.ai.gym_env import UltimateTKEnv, gym_available
    from ultimatetk.systems.gameplay_scene import GameplayScene
else:
    def gym_available() -> bool:
        return False


@unittest.skipUnless(np is not None and gym_available(), "gymnasium/numpy optional dependencies are not installed")
class GymEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        if not (PROJECT_ROOT / "game_data" / "palette.tab").exists():
            self.skipTest("game_data assets not available")

    def test_reset_returns_observation_shapes(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            observation, info = env.reset(seed=123)
            self.assertEqual(observation["rays"].shape, (32, 8))
            self.assertEqual(observation["state"].shape, (15,))
            self.assertEqual(info["level_index"], 0)
            self.assertFalse(info["game_completed"])
        finally:
            env.close()

    def test_death_marks_episode_terminated(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            env.reset(seed=5)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene) or scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("gameplay scene did not initialize")

            scene._player.dead = True  # type: ignore[attr-defined]

            action = {
                "hold": np.zeros((8,), dtype=np.int8),
                "trigger": np.zeros((1,), dtype=np.int8),
                "weapon_select": 0,
            }
            _, _, terminated, truncated, info = env.step(action)
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertEqual(info["terminal_reason"], "death")
        finally:
            env.close()

    def test_run_complete_marks_game_completed(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            env.reset(seed=7)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene) or scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("gameplay scene did not initialize")

            env._driver.context.session.level_index = 999
            scene._enemies.clear()  # type: ignore[attr-defined]

            action = {
                "hold": np.zeros((8,), dtype=np.int8),
                "trigger": np.zeros((1,), dtype=np.int8),
                "weapon_select": 0,
            }
            _, _, terminated, truncated, info = env.step(action)
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertTrue(info["game_completed"])
            self.assertEqual(info["terminal_reason"], "game_completed")
        finally:
            env.close()

    def test_replay_is_deterministic_under_fixed_seed(self) -> None:
        action_sequence = [
            {
                "hold": np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
            {
                "hold": np.array([1, 0, 1, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
            {
                "hold": np.array([0, 0, 0, 0, 1, 0, 1, 0], dtype=np.int8),
                "trigger": np.array([1], dtype=np.int8),
                "weapon_select": 0,
            },
            {
                "hold": np.zeros((8,), dtype=np.int8),
                "trigger": np.zeros((1,), dtype=np.int8),
                "weapon_select": 2,
            },
        ]

        def rollout() -> list[tuple[float, bool, bool, int, bool, str, float]]:
            env = UltimateTKEnv(
                project_root=str(PROJECT_ROOT),
                enforce_asset_manifest=True,
                max_episode_steps=120,
            )
            try:
                observation, _ = env.reset(seed=23)
                trace: list[tuple[float, bool, bool, int, bool, str, float]] = []
                for step in range(32):
                    action = action_sequence[step % len(action_sequence)]
                    observation, reward, terminated, truncated, info = env.step(action)
                    rays_sum = float(np.sum(observation["rays"]))
                    state_sum = float(np.sum(observation["state"]))
                    trace.append(
                        (
                            round(float(reward), 6),
                            bool(terminated),
                            bool(truncated),
                            int(info.get("level_index", 0)),
                            bool(info.get("game_completed", False)),
                            str(info.get("terminal_reason", "")),
                            round(rays_sum + state_sum, 6),
                        ),
                    )
                    if terminated or truncated:
                        break
                return trace
            finally:
                env.close()

        trace_a = rollout()
        trace_b = rollout()
        self.assertEqual(trace_a, trace_b)

    def test_weapon_mode_forces_selected_weapon_with_infinite_ammo_and_no_crates(self) -> None:
        env = UltimateTKEnv(
            project_root=str(PROJECT_ROOT),
            enforce_asset_manifest=True,
            weapon_mode="auto_rifle",
        )
        try:
            env.reset(seed=31)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene) or scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("gameplay scene did not initialize")

            player = scene._player  # type: ignore[attr-defined]
            self.assertTrue(player.infinite_ammo)
            self.assertEqual(player.current_weapon, 4)
            self.assertEqual(len(scene._crates), 0)  # type: ignore[attr-defined]
            self.assertEqual(env._driver.context.runtime.crates_total, 0)

            ammo_before = tuple(player.bullets)
            shoot_hold = np.array([0, 0, 0, 0, 0, 0, 1, 0], dtype=np.int8)
            idle_hold = np.zeros((8,), dtype=np.int8)
            no_trigger = np.zeros((1,), dtype=np.int8)

            for _ in range(8):
                env.step({"hold": shoot_hold, "trigger": no_trigger, "weapon_select": 0})
            env.step({"hold": idle_hold, "trigger": no_trigger, "weapon_select": 0})

            self.assertGreater(player.shots_fired_total, 0)
            self.assertEqual(tuple(player.bullets), ammo_before)
            self.assertEqual(player.current_weapon, 4)
            self.assertEqual(len(scene._crates), 0)  # type: ignore[attr-defined]
        finally:
            env.close()

    def test_randomized_reset_selects_level_from_pool(self) -> None:
        env = UltimateTKEnv(
            project_root=str(PROJECT_ROOT),
            enforce_asset_manifest=True,
            randomize_level_on_reset=True,
            level_index_pool=(0, 1, 2),
        )
        try:
            seen: set[int] = set()
            for seed in range(100, 124):
                _, info = env.reset(seed=seed)
                level_index = int(info.get("level_index", -1))
                self.assertIn(level_index, (0, 1, 2))
                seen.add(level_index)
            self.assertGreater(len(seen), 1)
        finally:
            env.close()

    def test_reset_option_level_index_overrides_randomized_selection(self) -> None:
        env = UltimateTKEnv(
            project_root=str(PROJECT_ROOT),
            enforce_asset_manifest=True,
            randomize_level_on_reset=True,
            level_index_pool=(0, 1, 2),
        )
        try:
            _, info = env.reset(seed=77, options={"level_index": 2})
            self.assertEqual(int(info.get("level_index", -1)), 2)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
