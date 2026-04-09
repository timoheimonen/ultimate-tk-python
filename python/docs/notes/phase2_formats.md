# Phase 2: Binary Format Parity

Implemented loaders under `python/src/ultimatetk/formats/`:

- `efp.py`
  - Reads EFP header (`"EF pic"`), dimensions, RLE payload, and 768-byte palette tail.
- `fnt.py`
  - Reads font width/height, 510-byte reserved header area, and 256 glyph bitmaps.
- `lev.py`
  - Parses versioned level structure (v1-v5), including blocks, starts, spots, steam, crate counts, and pointed crate data for v5.
- `palette_tab.py`
  - Parses `palette.tab` into trans/shadow/light lookup table blobs.
- `options_cfg.py`
  - Parses and writes the fixed-layout legacy options structure.

Supporting components:

- `python/src/ultimatetk/assets/repository.py`
  - High-level file access for case-insensitive lookup in `python/game_data/`.
- `python/tools/migrate_legacy_data.py`
  - Copies legacy asset folders/files into `python/game_data/`.
- `python/tools/format_probe.py`
  - Quick runtime parser probe against migrated data.

Verification:

- Unit tests in `python/tests/unit/` cover each format parser.
- Integration test in `python/tests/integration/test_real_data_parse.py` validates known real assets when available.
