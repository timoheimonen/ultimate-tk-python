# Game Data Packaging

The Python port must run using only data inside `python/`.

## Rule
- After migration is complete, the original repository root asset structure is not required for the Python version.
- Runtime asset loading must use `python/game_data/` paths only.

## Planned Source -> Destination Mapping
- `EFPS/` -> `python/game_data/efps/`
- `FNTS/` -> `python/game_data/fnts/`
- `LEVS/` -> `python/game_data/levs/`
- `MUSIC/` -> `python/game_data/music/`
- `WAVS/` -> `python/game_data/wavs/`
- `PALETTE.TAB` -> `python/game_data/palette.tab`
- `OPTIONS.CFG` -> `python/game_data/options.cfg` (or generated default on first run)

## Acceptance Check (End of Conversion)
- Python game starts and plays without reading assets from repository root.
- Temporarily renaming root asset folders does not break Python runtime.
