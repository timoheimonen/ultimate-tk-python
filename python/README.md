# Ultimate TK Python Port

This directory contains the Python refactor work.

## Current status
- Section 1 (architecture/runtime skeleton) is implemented.
- Section 2 (binary format parity loaders) is implemented.
- Section 3 rendering baseline is implemented with a software-style indexed renderer.
- Section 4 input/player control includes movement/collision/camera/weapon switching, shoot-reload cadence, and first-pass bi-directional combat (enemy spawn/aim/move/shoot + travel-time enemy projectiles + destructible/collectible crates with rewards + first-pass weapon ammo consumption/caps + ammo runtime telemetry snapshots for current weapon/full pools + first-pass shop trading helpers for ammo/weapons/shield/target + first-pass in-game shop flow with selection/transactions + player/enemy damage tracking + game-over flow).
- Combat and full gameplay systems are still in progress.

## Run the skeleton
From the `python/` directory:

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

Terminal controls:
- Movement/turn: `WASD` or arrow keys
- Strafe: `Q` / `E`
- Shoot: `Space`
- Next weapon: `Tab`
- Toggle shop: `R` or `Enter`
- Shop controls (while open): `W/S` rows, `A/D` columns, `Space` buy, `Tab` sell
- Direct weapon slot: `` ` ``, `1..0`, `-`
- Quit: `Esc`
- The terminal backend attempts to apply player1 keybinds from `python/game_data/options.cfg`; unsupported legacy scan codes fall back to defaults above.

## Notes
- Runtime data is expected under `python/game_data/`.
- The long-term goal is to run without depending on root-level legacy asset folders.

## Data migration helper
Copy legacy assets into `python/game_data/`:

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
