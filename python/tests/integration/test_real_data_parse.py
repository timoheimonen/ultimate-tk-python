from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.constants import REQUIRED_GAME_DATA_DIRS
from ultimatetk.core.paths import GamePaths


def _list_relative_files(directory: Path) -> list[str]:
    files = [path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()]
    files.sort()
    return files


def _casefold_index(files: list[str]) -> dict[str, str]:
    return {entry.upper(): entry for entry in files}


class RealDataParseTests(unittest.TestCase):
    def test_parse_known_assets(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        repo = GameDataRepository(paths)

        palette = repo.load_palette_tables()
        self.assertEqual(len(palette.trans_table), 256 * 256)

        efp = repo.load_efp("COOL.EFP")
        self.assertEqual((efp.width, efp.height), (320, 200))

        fnt = repo.load_fnt("8X8.FNT")
        self.assertEqual((fnt.glyph_width, fnt.glyph_height), (8, 8))

        lev = repo.load_lev("LEVEL1.LEV", episode="DEFAULT")
        self.assertEqual(lev.version, 1)
        self.assertGreater(lev.level_x_size, 0)
        self.assertGreater(lev.level_y_size, 0)

    def test_asset_manifest_required_files_exist(self) -> None:
        paths = GamePaths.discover()
        manifest_path = paths.game_data_root / "asset_manifest.json"
        self.assertTrue(manifest_path.is_file(), "missing python/game_data/asset_manifest.json")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required_files = manifest.get("required_files", [])
        self.assertTrue(required_files, "asset manifest required_files must not be empty")

        missing_files = [
            relative_path
            for relative_path in required_files
            if not (paths.game_data_root / relative_path).is_file()
        ]
        self.assertEqual(
            missing_files,
            [],
            f"missing required python/game_data assets: {missing_files}",
        )

    def test_graphics_and_sound_assets_match_legacy_source(self) -> None:
        paths = GamePaths.discover()
        manifest_path = paths.game_data_root / "asset_manifest.json"
        self.assertTrue(manifest_path.is_file(), "missing python/game_data/asset_manifest.json")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        categories = manifest.get("categories", {})

        legacy_root_env = os.getenv("ULTIMATETK_LEGACY_COMPARE_ROOT")
        if legacy_root_env is None:
            self.skipTest("set ULTIMATETK_LEGACY_COMPARE_ROOT to enable legacy parity comparison")

        legacy_root = Path(legacy_root_env).expanduser().resolve()
        compared = 0
        for category in categories.values():
            if category.get("kind") not in {"graphics", "sound"}:
                continue

            legacy_dir_name = category.get("legacy_dir")
            python_dir_name = category.get("python_dir")
            self.assertIsInstance(legacy_dir_name, str)
            self.assertIsInstance(python_dir_name, str)

            legacy_dir = legacy_root / legacy_dir_name
            self.assertTrue(legacy_dir.is_dir(), f"missing legacy asset directory: {legacy_dir}")

            python_dir = paths.game_data_root / python_dir_name
            self.assertTrue(python_dir.is_dir(), f"missing python asset directory: {python_dir}")

            legacy_files = _list_relative_files(legacy_dir)
            python_files = _list_relative_files(python_dir)
            legacy_index = _casefold_index(legacy_files)
            python_index = _casefold_index(python_files)
            missing_in_python = sorted(legacy_index.keys() - python_index.keys())
            extra_in_python = sorted(python_index.keys() - legacy_index.keys())

            self.assertEqual(
                missing_in_python,
                [],
                f"missing graphical/sound assets in python/{python_dir_name}: {missing_in_python}",
            )
            self.assertEqual(
                extra_in_python,
                [],
                f"unexpected graphical/sound assets in python/{python_dir_name}: {extra_in_python}",
            )
            compared += 1

        self.assertGreater(compared, 0, "expected at least one graphics/sound category in manifest")

    def test_game_application_fails_fast_on_missing_required_manifest_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_data = root / "game_data"
            for dirname in REQUIRED_GAME_DATA_DIRS:
                (game_data / dirname).mkdir(parents=True, exist_ok=True)

            manifest = {
                "manifest_version": 1,
                "required_files": ["efps/COOL.EFP"],
            }
            (game_data / "asset_manifest.json").write_text(
                f"{json.dumps(manifest)}\n",
                encoding="utf-8",
            )

            paths = GamePaths(
                python_root=root,
                game_data_root=game_data,
                runs_root=root / "runs",
            )
            with self.assertRaises(FileNotFoundError) as error_ctx:
                GameApplication.create(config=RuntimeConfig(session_auto_save=False), paths=paths)

            message = str(error_ctx.exception)
            self.assertIn("Missing required game data files", message)
            self.assertIn("efps/COOL.EFP", message)


if __name__ == "__main__":
    unittest.main()
