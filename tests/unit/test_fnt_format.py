from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.fnt import FNT_HEADER_RESERVED_SIZE, parse_fnt


class FntFormatTests(unittest.TestCase):
    def test_parse_fnt(self) -> None:
        glyph_width = 2
        glyph_height = 3
        glyph_size = glyph_width * glyph_height
        glyph_payload = bytes((i % 256 for i in range(glyph_size * 256)))
        data = bytes((glyph_width, glyph_height))
        data += bytes(FNT_HEADER_RESERVED_SIZE)
        data += glyph_payload

        font = parse_fnt(data)

        self.assertEqual(font.glyph_width, glyph_width)
        self.assertEqual(font.glyph_height, glyph_height)
        self.assertEqual(len(font.glyph_data), glyph_size * 256)
        self.assertEqual(font.glyph(0), glyph_payload[:glyph_size])
        self.assertEqual(font.glyph(65), glyph_payload[65 * glyph_size : 66 * glyph_size])

    def test_rejects_truncated_fnt(self) -> None:
        with self.assertRaises(ValueError):
            parse_fnt(b"\x08\x08")


if __name__ == "__main__":
    unittest.main()
