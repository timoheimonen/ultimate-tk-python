from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.paths import GamePaths


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


if __name__ == "__main__":
    unittest.main()
