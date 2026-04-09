from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IndexedFrameBuffer:
    width: int
    height: int
    pixels: bytearray

    def __init__(self, width: int, height: int, fill: int = 0) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("framebuffer dimensions must be positive")
        if fill < 0 or fill > 255:
            raise ValueError("fill color must be in range 0..255")

        self.width = width
        self.height = height
        self.pixels = bytearray([fill]) * (width * height)

    def clear(self, color: int = 0) -> None:
        if color < 0 or color > 255:
            raise ValueError("clear color must be in range 0..255")
        self.pixels[:] = bytearray([color]) * (self.width * self.height)

    def as_bytes(self) -> bytes:
        return bytes(self.pixels)

    def blit_opaque(
        self,
        src: bytes,
        src_width: int,
        src_height: int,
        dst_x: int,
        dst_y: int,
        *,
        src_x: int = 0,
        src_y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        rect = self._resolve_rect(
            dst_x=dst_x,
            dst_y=dst_y,
            src_x=src_x,
            src_y=src_y,
            width=width,
            height=height,
            src_width=src_width,
            src_height=src_height,
        )
        if rect is None:
            return

        dst_x, dst_y, src_x, src_y, width, height = rect
        for row in range(height):
            src_start = (src_y + row) * src_width + src_x
            dst_start = (dst_y + row) * self.width + dst_x
            self.pixels[dst_start : dst_start + width] = src[src_start : src_start + width]

    def blit_transparent(
        self,
        src: bytes,
        src_width: int,
        src_height: int,
        dst_x: int,
        dst_y: int,
        *,
        transparent_index: int = 0,
        src_x: int = 0,
        src_y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        rect = self._resolve_rect(
            dst_x=dst_x,
            dst_y=dst_y,
            src_x=src_x,
            src_y=src_y,
            width=width,
            height=height,
            src_width=src_width,
            src_height=src_height,
        )
        if rect is None:
            return

        dst_x, dst_y, src_x, src_y, width, height = rect
        for row in range(height):
            src_row_start = (src_y + row) * src_width + src_x
            dst_row_start = (dst_y + row) * self.width + dst_x
            for col in range(width):
                value = src[src_row_start + col]
                if value != transparent_index:
                    self.pixels[dst_row_start + col] = value

    def blit_translucent(
        self,
        src: bytes,
        src_width: int,
        src_height: int,
        dst_x: int,
        dst_y: int,
        *,
        trans_table: bytes,
        transparent_index: int = 0,
        src_x: int = 0,
        src_y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        if len(trans_table) != 256 * 256:
            raise ValueError("trans_table must be 65536 bytes")

        rect = self._resolve_rect(
            dst_x=dst_x,
            dst_y=dst_y,
            src_x=src_x,
            src_y=src_y,
            width=width,
            height=height,
            src_width=src_width,
            src_height=src_height,
        )
        if rect is None:
            return

        dst_x, dst_y, src_x, src_y, width, height = rect
        for row in range(height):
            src_row_start = (src_y + row) * src_width + src_x
            dst_row_start = (dst_y + row) * self.width + dst_x
            for col in range(width):
                src_color = src[src_row_start + col]
                if src_color == transparent_index:
                    continue
                dst_index = dst_row_start + col
                dst_color = self.pixels[dst_index]
                self.pixels[dst_index] = trans_table[src_color * 256 + dst_color]

    def apply_shadow(
        self,
        mask: bytes,
        mask_width: int,
        mask_height: int,
        dst_x: int,
        dst_y: int,
        *,
        shadow_table: bytes,
        src_x: int = 0,
        src_y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        if len(shadow_table) != 256 * 16:
            raise ValueError("shadow_table must be 4096 bytes")

        rect = self._resolve_rect(
            dst_x=dst_x,
            dst_y=dst_y,
            src_x=src_x,
            src_y=src_y,
            width=width,
            height=height,
            src_width=mask_width,
            src_height=mask_height,
        )
        if rect is None:
            return

        dst_x, dst_y, src_x, src_y, width, height = rect
        for row in range(height):
            src_row_start = (src_y + row) * mask_width + src_x
            dst_row_start = (dst_y + row) * self.width + dst_x
            for col in range(width):
                shade = mask[src_row_start + col]
                if shade == 0:
                    continue
                dst_index = dst_row_start + col
                dst_color = self.pixels[dst_index]
                self.pixels[dst_index] = shadow_table[dst_color * 16 + shade]

    def apply_light(
        self,
        mask: bytes,
        mask_width: int,
        mask_height: int,
        dst_x: int,
        dst_y: int,
        *,
        light_table: bytes,
        add: int = 0,
        src_x: int = 0,
        src_y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        if len(light_table) != 256 * 16:
            raise ValueError("light_table must be 4096 bytes")

        rect = self._resolve_rect(
            dst_x=dst_x,
            dst_y=dst_y,
            src_x=src_x,
            src_y=src_y,
            width=width,
            height=height,
            src_width=mask_width,
            src_height=mask_height,
        )
        if rect is None:
            return

        dst_x, dst_y, src_x, src_y, width, height = rect
        for row in range(height):
            src_row_start = (src_y + row) * mask_width + src_x
            dst_row_start = (dst_y + row) * self.width + dst_x
            for col in range(width):
                power = mask[src_row_start + col]
                if power == 0:
                    continue

                lum = power + add
                if lum < 0:
                    lum = 0
                elif lum > 15:
                    lum = 15

                dst_index = dst_row_start + col
                dst_color = self.pixels[dst_index]
                self.pixels[dst_index] = light_table[dst_color * 16 + lum]

    def _resolve_rect(
        self,
        *,
        dst_x: int,
        dst_y: int,
        src_x: int,
        src_y: int,
        width: int | None,
        height: int | None,
        src_width: int,
        src_height: int,
    ) -> tuple[int, int, int, int, int, int] | None:
        if src_width <= 0 or src_height <= 0:
            return None

        if src_x >= src_width or src_y >= src_height:
            return None

        if width is None:
            width = src_width - src_x
        if height is None:
            height = src_height - src_y

        if width <= 0 or height <= 0:
            return None

        if src_x < 0:
            dst_x -= src_x
            width += src_x
            src_x = 0
        if src_y < 0:
            dst_y -= src_y
            height += src_y
            src_y = 0

        if dst_x < 0:
            src_x -= dst_x
            width += dst_x
            dst_x = 0
        if dst_y < 0:
            src_y -= dst_y
            height += dst_y
            dst_y = 0

        if src_x >= src_width or src_y >= src_height:
            return None
        if dst_x >= self.width or dst_y >= self.height:
            return None

        width = min(width, src_width - src_x, self.width - dst_x)
        height = min(height, src_height - src_y, self.height - dst_y)
        if width <= 0 or height <= 0:
            return None

        return (dst_x, dst_y, src_x, src_y, width, height)
