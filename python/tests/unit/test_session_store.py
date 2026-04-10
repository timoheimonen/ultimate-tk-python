from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.paths import GamePaths
from ultimatetk.core.session_store import load_persisted_session, save_persisted_session, session_profile_path
from ultimatetk.core.state import SessionState


class SessionStoreTests(unittest.TestCase):
    def _paths(self, root: Path) -> GamePaths:
        return GamePaths(
            python_root=root,
            game_data_root=root / "game_data",
            runs_root=root / "runs",
        )

    def test_save_then_load_session_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)

            save_persisted_session(
                paths,
                SessionState(player_name="Delta", episode_index=3, level_index=7),
            )

            loaded = load_persisted_session(paths)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.player_name, "Delta")
            self.assertEqual(loaded.episode_index, 3)
            self.assertEqual(loaded.level_index, 7)

    def test_load_missing_profile_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            self.assertIsNone(load_persisted_session(paths))

    def test_save_profile_payload_contains_expected_fields_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            save_persisted_session(
                paths,
                SessionState(player_name="Rambo", episode_index=1, level_index=2),
            )

            payload = json.loads(session_profile_path(paths).read_text(encoding="utf-8"))
            self.assertEqual(sorted(payload.keys()), ["episode_index", "level_index", "player_name", "version"])
            self.assertEqual(payload["player_name"], "Rambo")


if __name__ == "__main__":
    unittest.main()
