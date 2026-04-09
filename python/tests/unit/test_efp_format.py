from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.efp import PALETTE_SIZE, parse_efp


class EfpFormatTests(unittest.TestCase):
    def test_parse_minimal_efp(self) -> None:
        header = b"EF pic" + bytes((4, 0, 1, 0))
        rle_stream = bytes((5, 194, 7, 9))
        palette = bytes((i % 256 for i in range(PALETTE_SIZE)))
        data = header + rle_stream + palette

        image = parse_efp(data)

        self.assertEqual(image.width, 4)
        self.assertEqual(image.height, 1)
        self.assertEqual(image.pixels, bytes((5, 7, 7, 9)))
        self.assertEqual(image.palette, palette)

    def test_rejects_invalid_magic(self) -> None:
        with self.assertRaises(ValueError):
            parse_efp(b"NOT_EF" + bytes(1000))


if __name__ == "__main__":
    unittest.main()
