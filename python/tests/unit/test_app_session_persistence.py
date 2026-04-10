from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.constants import REQUIRED_GAME_DATA_DIRS
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.session_store import load_persisted_session, save_persisted_session, session_profile_path
from ultimatetk.core.state import SessionState


class AppSessionPersistenceTests(unittest.TestCase):
    def _prepare_paths(self, root: Path) -> GamePaths:
        game_data = root / "game_data"
        for dirname in REQUIRED_GAME_DATA_DIRS:
            (game_data / dirname).mkdir(parents=True, exist_ok=True)
        return GamePaths(
            python_root=root,
            game_data_root=game_data,
            runs_root=root / "runs",
        )

    def test_create_loads_persisted_session_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._prepare_paths(root)
            save_persisted_session(
                paths,
                SessionState(player_name="Loader", episode_index=4, level_index=6),
            )

            app = GameApplication.create(
                config=RuntimeConfig(
                    session_load_on_start=True,
                    session_auto_save=False,
                    enforce_asset_manifest=False,
                ),
                paths=paths,
            )

            self.assertEqual(app.context.session.player_name, "Loader")
            self.assertEqual(app.context.session.episode_index, 4)
            self.assertEqual(app.context.session.level_index, 6)

    def test_create_new_session_overwrites_existing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._prepare_paths(root)
            save_persisted_session(
                paths,
                SessionState(player_name="Old", episode_index=2, level_index=9),
            )

            app = GameApplication.create(
                config=RuntimeConfig(
                    session_new_on_start=True,
                    session_auto_save=False,
                    enforce_asset_manifest=False,
                ),
                paths=paths,
            )

            self.assertEqual(app.context.session.player_name, "Player1")
            self.assertEqual(app.context.session.episode_index, 0)
            self.assertEqual(app.context.session.level_index, 0)

            persisted = load_persisted_session(paths)
            self.assertIsNotNone(persisted)
            assert persisted is not None
            self.assertEqual(persisted.player_name, "Player1")
            self.assertEqual(persisted.episode_index, 0)
            self.assertEqual(persisted.level_index, 0)

    def test_invalid_load_and_new_session_combination_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._prepare_paths(root)

            with self.assertRaises(ValueError):
                GameApplication.create(
                    config=RuntimeConfig(
                        session_load_on_start=True,
                        session_new_on_start=True,
                        enforce_asset_manifest=False,
                    ),
                    paths=paths,
                )

    def test_run_auto_saves_session_profile_on_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._prepare_paths(root)

            app = GameApplication.create(
                config=RuntimeConfig(
                    max_seconds=0.0,
                    session_auto_save=True,
                    enforce_asset_manifest=False,
                ),
                paths=paths,
            )
            app.context.session.player_name = "Saver"
            app.context.session.episode_index = 5
            app.context.session.level_index = 3

            exit_code = app.run()

            self.assertEqual(exit_code, 0)
            self.assertTrue(session_profile_path(paths).exists())
            persisted = load_persisted_session(paths)
            self.assertIsNotNone(persisted)
            assert persisted is not None
            self.assertEqual(persisted.player_name, "Saver")
            self.assertEqual(persisted.episode_index, 5)
            self.assertEqual(persisted.level_index, 3)


if __name__ == "__main__":
    unittest.main()
