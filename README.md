# Ultimate TK Python Port

This repository hosts the Python refactor at root level.

## Current status
- Phases 1-9 are completed (runtime, formats, rendering, controls/combat, UI/progression, parity tuning, regression suite, and data-colocation hardening).
- Phase 10 is completed:
  - root-level project layout is active (no `python/` wrapper directory),
  - legacy DOS-era payload is archived under `ARCHIVE/`,
  - legacy parity checks are optional (default verification works without legacy root asset folders).
- Phase 11 is in progress:
  - optional pygame runtime backend is wired behind `--platform pygame`,
  - gameplay render payload handoff is available for window presentation,
  - pygame dependency remains optional.

## Run

Run from repository root:

```bash
PYTHONPATH=src python3 -m ultimatetk --max-seconds 2 --autostart-gameplay --status-print-interval 40
```

Replay scripted input in headless mode:

```bash
PYTHONPATH=src python3 -m ultimatetk --max-seconds 1.2 --autostart-gameplay --status-print-interval 20 --input-script "5:+MOVE_FORWARD;25:-MOVE_FORWARD;30:+TURN_LEFT;36:-TURN_LEFT"
```

Run with terminal keyboard input (interactive TTY required):

```bash
PYTHONPATH=src python3 -m ultimatetk --platform terminal --autostart-gameplay --status-print-interval 20
```

Run with pygame window backend (optional dependency):

```bash
PYTHONPATH=src python3 -m ultimatetk --platform pygame --autostart-gameplay --window-scale 3
```

Optional scale examples:

- `--window-scale 2` -> `640x400`
- `--window-scale 3` -> `960x600`

Install pygame extras (if needed):

```bash
python3 -m pip install -e ".[pygame]"
```

## Release verification

Default release bundle (no legacy root dependency):

```bash
python3 tools/release_verification.py
```

Optional strict parity against archived legacy sources:

```bash
python3 tools/release_verification.py --legacy-compare-root ARCHIVE
```

Terminal controls:
- Movement/turn: `WASD` or arrow keys
- Strafe: `Q` / `E`
- Shoot: `Space`
- Next weapon: `Tab`
- Toggle shop: `R` or `Enter`
- Shop controls (while open): `W/S` rows, `A/D` columns, `Space` buy, `Tab` sell
- Direct weapon slot: `` ` ``, `1..0`, `-`
- Quit: `Esc`
- The terminal backend attempts to apply player1 keybinds from `game_data/options.cfg`; unsupported legacy scan codes fall back to defaults above.

## Data layout

- Runtime assets: `game_data/`
- Archived original payload: `ARCHIVE/`
- Runtime diagnostics: `runs/`
- Phase notes: `docs/notes/`

## Tooling

Regenerate manifest and gap list:

```bash
python3 tools/asset_manifest_report.py
```

Copy legacy assets into `game_data/` from `ARCHIVE/`:

```bash
python3 tools/migrate_legacy_data.py
```

Probe format loaders against migrated data:

```bash
python3 tools/format_probe.py
```

Render a baseline gameplay frame to a screenshot:

```bash
python3 tools/render_probe.py --output runs/screenshots/phase3_render_probe.ppm
```
