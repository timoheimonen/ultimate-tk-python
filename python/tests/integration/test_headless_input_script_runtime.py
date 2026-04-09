from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.paths import GamePaths


class HeadlessInputScriptRuntimeTests(unittest.TestCase):
    def test_scripted_turn_changes_player_angle(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.6,
            input_script="5:+TURN_LEFT;11:-TURN_LEFT",
        )
        app = GameApplication.create(config=config, paths=paths)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertNotEqual(app.context.runtime.player_angle_degrees, 0)

    def test_scripted_shoot_increments_shot_counter(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        config = RuntimeConfig(
            autostart_gameplay=True,
            max_seconds=0.8,
            input_script="5:+SHOOT;40:-SHOOT",
        )
        app = GameApplication.create(config=config, paths=paths)

        exit_code = app.run()

        self.assertEqual(exit_code, 0)
        self.assertGreater(app.context.runtime.player_shots_fired_total, 0)
        self.assertGreaterEqual(app.context.runtime.enemies_total, app.context.runtime.enemies_alive)


if __name__ == "__main__":
    unittest.main()
