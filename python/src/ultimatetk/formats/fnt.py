from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultimatetk.formats._binary import BinaryReader


FNT_HEADER_RESERVED_SIZE = 510


@dataclass(frozen=True, slots=True)
class FontFile:
    glyph_width: int
    glyph_height: int
    reserved_header: bytes
    glyph_data: bytes

    @property
    def glyph_size(self) -> int:
        return self.glyph_width * self.glyph_height

    def glyph(self, codepoint: int) -> bytes:
        if codepoint < 0 or codepoint > 255:
            raise ValueError("codepoint must be in range 0..255")
        start = codepoint * self.glyph_size
        end = start + self.glyph_size
        return self.glyph_data[start:end]


def parse_fnt(data: bytes) -> FontFile:
    reader = BinaryReader(data=data)
    if reader.remaining < 2:
        raise ValueError("data too short for FNT header")

    glyph_width = reader.read_u8()
    glyph_height = reader.read_u8()
    reserved_header = reader.read_bytes(FNT_HEADER_RESERVED_SIZE)

    glyph_size = glyph_width * glyph_height
    expected_payload = glyph_size * 256
    payload = reader.read_bytes(expected_payload)

    return FontFile(
        glyph_width=glyph_width,
        glyph_height=glyph_height,
        reserved_header=reserved_header,
        glyph_data=payload,
    )


def load_fnt(path: str | Path) -> FontFile:
    file_path = Path(path)
    return parse_fnt(file_path.read_bytes())
