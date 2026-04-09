from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultimatetk.formats._binary import BinaryReader


EFP_MAGIC = b"EF pic"
PALETTE_SIZE = 768


@dataclass(frozen=True, slots=True)
class EfpImage:
    width: int
    height: int
    pixels: bytes
    palette: bytes


def parse_efp(data: bytes, offset: int = 0) -> EfpImage:
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if offset + 10 > len(data):
        raise ValueError("data too short for EFP header")

    reader = BinaryReader(data=data, offset=offset)
    magic = reader.read_bytes(6)
    if magic != EFP_MAGIC:
        raise ValueError("file is not an EFP image")

    width = reader.read_u16_le()
    height = reader.read_u16_le()
    pixel_count = width * height

    decoded = bytearray()
    while len(decoded) < pixel_count:
        if reader.remaining <= 0:
            raise ValueError("unexpected end of EFP RLE stream")
        token = reader.read_u8()
        if token > 192:
            run_length = token - 192
            if reader.remaining <= 0:
                raise ValueError("truncated EFP RLE run")
            value = reader.read_u8()
            decoded.extend(bytes((value,)) * run_length)
        else:
            decoded.append(token)

    if len(decoded) != pixel_count:
        raise ValueError("decoded EFP pixel count mismatch")

    if len(data) < PALETTE_SIZE:
        raise ValueError("data too short for EFP palette")
    palette = data[-PALETTE_SIZE:]

    return EfpImage(
        width=width,
        height=height,
        pixels=bytes(decoded),
        palette=palette,
    )


def load_efp(path: str | Path, offset: int = 0) -> EfpImage:
    file_path = Path(path)
    return parse_efp(file_path.read_bytes(), offset=offset)


def load_efp_palette(path: str | Path) -> bytes:
    file_path = Path(path)
    data = file_path.read_bytes()
    if len(data) < PALETTE_SIZE:
        raise ValueError(f"EFP file too short for palette: {file_path}")
    return data[-PALETTE_SIZE:]
