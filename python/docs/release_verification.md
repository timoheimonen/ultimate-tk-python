# Release Verification Runbook

Use this runbook for repeatable release validation after Phase 9 hardening.

## Preferred command

Run the bundled verifier from repository root:

```bash
python3 python/tools/release_verification.py
```

This executes:

1. Asset manifest + gap regeneration (`python/tools/asset_manifest_report.py`)
2. Unit verification matrix
3. Integration verification matrix

## Optional flags

- `--skip-manifest`: skip manifest/gap regeneration
- `--skip-unit`: skip unit matrix
- `--skip-integration`: skip integration matrix
- `--legacy-compare-root <path>`: enable strict parity comparison against legacy source directories

Example:

```bash
python3 python/tools/release_verification.py --skip-integration
```

Run with strict legacy parity against archived original sources:

```bash
python3 python/tools/release_verification.py --legacy-compare-root ARCHIVE
```

## Direct command bundle

If needed, run steps manually inside `python/`:

```bash
python3 tools/asset_manifest_report.py
python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py
python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py
```

## Artifact hygiene

- Runtime diagnostics stay under `python/runs/`.
- Do not commit runtime profile JSON files or generated screenshot dumps.
- Keep tracked placeholder files (for example `python/runs/screenshots/.gitkeep`) in place.
