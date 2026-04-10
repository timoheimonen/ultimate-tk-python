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


def _action(*, hold: np.ndarray | None = None, trigger: np.ndarray | None = None) -> dict[str, np.ndarray | int]:
    return {
        "hold": np.zeros((8,), dtype=np.int8) if hold is None else hold,
        "trigger": np.zeros((2,), dtype=np.int8) if trigger is None else trigger,
        "weapon_select": 0,
    }


@unittest.skipUnless(np is not None and gym_available(), "gymnasium/numpy optional dependencies are not installed")
class GymEnvShopProgressionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not (PROJECT_ROOT / "game_data" / "palette.tab").exists():
            self.skipTest("game_data assets not available")

    def test_shop_purchase_carries_over_after_level_progression(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            env.reset(seed=13)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene) or scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("gameplay scene did not initialize")

            has_next = scene._level_exists_for_session_index(env._driver.context, 1)  # type: ignore[attr-defined]
            if not has_next:
                self.skipTest("next level asset missing for progression test")

            player = scene._player  # type: ignore[attr-defined]
            player.cash = 5000
            scene._shop_row = 1  # ammo row  # type: ignore[attr-defined]
            scene._shop_column = 0  # type: ignore[attr-defined]

            env.step(_action(trigger=np.array([0, 1], dtype=np.int8)))
            env.step(_action(hold=np.array([0, 0, 0, 0, 0, 0, 1, 0], dtype=np.int8)))
            env.step(_action())
            env.step(_action(trigger=np.array([0, 1], dtype=np.int8)))

            purchased_units = int(player.bullets[0])
            self.assertGreater(purchased_units, 0)

            scene._enemies.clear()  # type: ignore[attr-defined]
            env.step(_action())
            env.step(_action(trigger=np.array([1, 0], dtype=np.int8)))
            env.step(_action())

            next_scene = env._driver.scene_manager.current_scene
            if not isinstance(next_scene, GameplayScene) or next_scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("failed to return to gameplay scene")

            next_player = next_scene._player  # type: ignore[attr-defined]
            self.assertGreaterEqual(int(next_player.bullets[0]), purchased_units)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
