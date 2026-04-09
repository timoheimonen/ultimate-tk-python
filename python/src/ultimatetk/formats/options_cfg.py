from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from ultimatetk.formats._binary import BinaryReader, decode_c_string, encode_c_string


KEYS_COUNT = 9
OPTIONS_CFG_SIZE = 145


@dataclass(frozen=True, slots=True)
class KeysConfig:
    k_left: int
    k_right: int
    k_up: int
    k_down: int
    k_shoot: int
    k_shift: int
    k_strafe: int
    k_lstrafe: int
    k_rstrafe: int

    def as_tuple(self) -> tuple[int, ...]:
        return (
            self.k_left,
            self.k_right,
            self.k_up,
            self.k_down,
            self.k_shoot,
            self.k_shift,
            self.k_strafe,
            self.k_lstrafe,
            self.k_rstrafe,
        )


@dataclass(frozen=True, slots=True)
class OptionsConfig:
    keys1: KeysConfig
    keys2: KeysConfig
    name1: str
    name2: str
    dark_mode: int
    light_effects: int
    shadows: int
    music_volume: int
    effect_volume: int
    enemies_on_game: int
    death_match_level: str
    death_match_episode: int
    death_match_speed: int
    saved_killing_mode: int
    saved_game_mode: int


def parse_options_cfg(data: bytes) -> OptionsConfig:
    if len(data) < OPTIONS_CFG_SIZE:
        raise ValueError(
            f"options.cfg too short: expected at least {OPTIONS_CFG_SIZE}, got {len(data)}",
        )

    reader = BinaryReader(data=data[:OPTIONS_CFG_SIZE])
    keys1 = KeysConfig(*reader.read_i32_array(KEYS_COUNT))
    keys2 = KeysConfig(*reader.read_i32_array(KEYS_COUNT))

    name1 = decode_c_string(reader.read_bytes(10))
    name2 = decode_c_string(reader.read_bytes(10))

    dark_mode = reader.read_i32_le()
    light_effects = reader.read_i32_le()
    shadows = reader.read_i32_le()
    music_volume = reader.read_i32_le()
    effect_volume = reader.read_i32_le()
    enemies_on_game = reader.read_i32_le()
    death_match_level = decode_c_string(reader.read_bytes(13))
    death_match_episode = reader.read_i32_le()
    death_match_speed = reader.read_i32_le()
    saved_killing_mode = reader.read_i32_le()
    saved_game_mode = reader.read_i32_le()

    return OptionsConfig(
        keys1=keys1,
        keys2=keys2,
        name1=name1,
        name2=name2,
        dark_mode=dark_mode,
        light_effects=light_effects,
        shadows=shadows,
        music_volume=music_volume,
        effect_volume=effect_volume,
        enemies_on_game=enemies_on_game,
        death_match_level=death_match_level,
        death_match_episode=death_match_episode,
        death_match_speed=death_match_speed,
        saved_killing_mode=saved_killing_mode,
        saved_game_mode=saved_game_mode,
    )


def encode_options_cfg(config: OptionsConfig) -> bytes:
    output = bytearray()
    output.extend(struct.pack("<9i", *config.keys1.as_tuple()))
    output.extend(struct.pack("<9i", *config.keys2.as_tuple()))
    output.extend(encode_c_string(config.name1, 10))
    output.extend(encode_c_string(config.name2, 10))
    output.extend(struct.pack("<i", config.dark_mode))
    output.extend(struct.pack("<i", config.light_effects))
    output.extend(struct.pack("<i", config.shadows))
    output.extend(struct.pack("<i", config.music_volume))
    output.extend(struct.pack("<i", config.effect_volume))
    output.extend(struct.pack("<i", config.enemies_on_game))
    output.extend(encode_c_string(config.death_match_level, 13))
    output.extend(struct.pack("<i", config.death_match_episode))
    output.extend(struct.pack("<i", config.death_match_speed))
    output.extend(struct.pack("<i", config.saved_killing_mode))
    output.extend(struct.pack("<i", config.saved_game_mode))

    if len(output) != OPTIONS_CFG_SIZE:
        raise RuntimeError(f"encoded options.cfg has invalid size: {len(output)}")
    return bytes(output)


def load_options_cfg(path: str | Path) -> OptionsConfig:
    file_path = Path(path)
    return parse_options_cfg(file_path.read_bytes())


def save_options_cfg(path: str | Path, config: OptionsConfig) -> None:
    file_path = Path(path)
    file_path.write_bytes(encode_options_cfg(config))
