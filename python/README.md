# Ultimate TK Python Port

This directory contains the Python refactor work.

## Current status
- Section 1 (architecture/runtime skeleton) is implemented.
- Rendering and gameplay features are placeholders.

## Run the skeleton
From the `python/` directory:

```bash
PYTHONPATH=src python3 -m ultimatetk --max-seconds 2 --autostart-gameplay --status-print-interval 40
```

## Notes
- Runtime data is expected under `python/game_data/`.
- The long-term goal is to run without depending on root-level legacy asset folders.
