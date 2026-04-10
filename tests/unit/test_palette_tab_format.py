from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.palette_tab import PALETTE_TAB_SIZE, parse_palette_tab


class PaletteTabFormatTests(unittest.TestCase):
    def test_parse_palette_tab(self) -> None:
        data = bytes((i % 256 for i in range(PALETTE_TAB_SIZE)))
        tables = parse_palette_tab(data)

        self.assertEqual(len(tables.trans_table), 256 * 256)
        self.assertEqual(len(tables.shadow_table), 256 * 16)
        self.assertEqual(len(tables.normal_light_table), 256 * 16)
        self.assertEqual(len(tables.red_light_table), 256 * 16)
        self.assertEqual(len(tables.yellow_light_table), 256 * 16)
        self.assertEqual(len(tables.explo_light_table), 256 * 16)
        self.assertEqual(tables.trans_table[0], 0)
        self.assertEqual(tables.explo_light_table[-1], data[-1])

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(ValueError):
            parse_palette_tab(b"\x00" * (PALETTE_TAB_SIZE - 1))


if __name__ == "__main__":
    unittest.main()
