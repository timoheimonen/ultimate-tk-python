from __future__ import annotations

from pathlib import Path


def _expand_vga_channel(value: int) -> int:
    if value < 0:
        value = 0
    elif value > 63:
        value = 63
    return (value * 255) // 63


def build_rgb_palette(raw_palette: bytes) -> bytes:
    if len(raw_palette) != 256 * 3:
        raise ValueError("palette must be exactly 768 bytes")

    rgb_palette = bytearray(256 * 3)
    for index in range(256):
        src = index * 3
        dst = src
        rgb_palette[dst + 0] = _expand_vga_channel(raw_palette[src + 0])
        rgb_palette[dst + 1] = _expand_vga_channel(raw_palette[src + 1])
        rgb_palette[dst + 2] = _expand_vga_channel(raw_palette[src + 2])
    return bytes(rgb_palette)


def indexed_to_rgb24(pixels: bytes, raw_palette: bytes) -> bytes:
    rgb_palette = build_rgb_palette(raw_palette)
    rgb = bytearray(len(pixels) * 3)
    for idx, color in enumerate(pixels):
        src = color * 3
        dst = idx * 3
        rgb[dst : dst + 3] = rgb_palette[src : src + 3]
    return bytes(rgb)


def write_indexed_ppm(
    path: str | Path,
    pixels: bytes,
    width: int,
    height: int,
    raw_palette: bytes,
) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if len(pixels) != width * height:
        raise ValueError("pixel buffer size does not match width*height")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rgb = indexed_to_rgb24(pixels, raw_palette)
    with output_path.open("wb") as fp:
        fp.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        fp.write(rgb)
