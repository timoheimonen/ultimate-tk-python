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
        "trigger": np.zeros((1,), dtype=np.int8) if trigger is None else trigger,
        "weapon_select": 0,
    }


@unittest.skipUnless(np is not None and gym_available(), "gymnasium/numpy optional dependencies are not installed")
class GymEnvShopProgressionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not (PROJECT_ROOT / "game_data" / "palette.tab").exists():
            self.skipTest("game_data assets not available")

    def test_env_action_model_cannot_open_shop(self) -> None:
        env = UltimateTKEnv(project_root=str(PROJECT_ROOT), enforce_asset_manifest=True)
        try:
            env.reset(seed=13)

            assert env._driver is not None
            scene = env._driver.scene_manager.current_scene
            if not isinstance(scene, GameplayScene) or scene._player is None:  # type: ignore[attr-defined]
                self.skipTest("gameplay scene did not initialize")

            runtime = env._driver.context.runtime
            self.assertFalse(runtime.shop_active)

            env.step(_action(trigger=np.array([1], dtype=np.int8)))
            env.step(_action(hold=np.array([0, 0, 0, 0, 0, 0, 1, 0], dtype=np.int8)))
            env.step(_action())
            env.step(_action(trigger=np.array([1], dtype=np.int8)))

            self.assertFalse(runtime.shop_active)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
