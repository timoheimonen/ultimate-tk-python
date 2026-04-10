from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.formats.options_cfg import (
    KEYS_COUNT,
    OPTIONS_CFG_SIZE,
    KeysConfig,
    OptionsConfig,
    encode_options_cfg,
    parse_options_cfg,
)


class OptionsCfgFormatTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        keys1 = KeysConfig(*range(1, KEYS_COUNT + 1))
        keys2 = KeysConfig(*range(11, 11 + KEYS_COUNT))
        original = OptionsConfig(
            keys1=keys1,
            keys2=keys2,
            name1="PlayerOne",
            name2="PlayerTwo",
            dark_mode=1,
            light_effects=1,
            shadows=0,
            music_volume=42,
            effect_volume=55,
            enemies_on_game=1,
            death_match_level="LEVEL1.LEV",
            death_match_episode=2,
            death_match_speed=3,
            saved_killing_mode=0,
            saved_game_mode=1,
        )

        encoded = encode_options_cfg(original)
        decoded = parse_options_cfg(encoded)

        self.assertEqual(len(encoded), OPTIONS_CFG_SIZE)
        self.assertEqual(decoded, original)

    def test_rejects_truncated_file(self) -> None:
        with self.assertRaises(ValueError):
            parse_options_cfg(b"\x00" * (OPTIONS_CFG_SIZE - 10))


if __name__ == "__main__":
    unittest.main()
