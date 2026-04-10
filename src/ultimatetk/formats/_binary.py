from __future__ import annotations

from dataclasses import dataclass
import struct


@dataclass(slots=True)
class BinaryReader:
    data: bytes
    offset: int = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read_bytes(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must be non-negative")
        end = self.offset + size
        if end > len(self.data):
            raise ValueError(
                f"unexpected end of data at offset {self.offset}, "
                f"needed {size} bytes",
            )
        chunk = self.data[self.offset:end]
        self.offset = end
        return chunk

    def read_u8(self) -> int:
        return self.read_bytes(1)[0]

    def read_u16_le(self) -> int:
        raw = self.read_bytes(2)
        return struct.unpack("<H", raw)[0]

    def read_i32_le(self) -> int:
        raw = self.read_bytes(4)
        return struct.unpack("<i", raw)[0]

    def read_i32_array(self, count: int) -> tuple[int, ...]:
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return ()
        raw = self.read_bytes(count * 4)
        return struct.unpack(f"<{count}i", raw)


def decode_c_string(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("latin-1")


def encode_c_string(value: str, length: int) -> bytes:
    if length <= 0:
        raise ValueError("length must be positive")
    encoded = value.encode("latin-1", errors="replace")
    if len(encoded) >= length:
        encoded = encoded[: length - 1]
    return encoded + (b"\x00" * (length - len(encoded)))
