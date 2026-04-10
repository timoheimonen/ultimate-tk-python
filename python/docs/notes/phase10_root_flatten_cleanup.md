# Phase 10: Root Flatten and Legacy Cleanup (Checklist Plan)

This checklist defines the execution order for moving the Python project from `python/` to repository root while making legacy asset comparison optional and removing original game-data folders.

## Preconditions

- [ ] Confirm current branch is clean.
- [ ] Confirm Phase 9 release verification bundle passes before any path moves.
- [ ] Record a baseline verification snapshot:
  - [ ] `python3 python/tools/release_verification.py`

## Workstream 1: Make legacy-compare optional

- [x] Update `tests/integration/test_real_data_parse.py`:
  - [x] Default mode passes without legacy root directories.
  - [x] Legacy parity checks run only when explicit legacy-compare mode is enabled.
- [x] Update `tools/asset_manifest_report.py`:
  - [x] Default mode builds/validates from `game_data` only.
  - [x] Optional strict compare mode accepts explicit `--legacy-root`.
- [x] Update `tools/release_verification.py`:
  - [x] Default release bundle does not require legacy roots.
  - [x] Optional legacy compare switch/path is supported.
- [x] Verification gate:
  - [x] Run unit matrix.
  - [x] Run integration matrix.
  - [x] Run release verifier in default mode.

## Workstream 2: Resolve root-level name conflicts

- [x] Inventory root paths that conflict with Python-root layout on case-insensitive filesystems:
  - [x] `SRC/` vs future `src/`
  - [x] `LICENSE` vs `python/LICENSE`
- [x] Choose destination for retained legacy code/binaries:
  - [x] Move to `ARCHIVE/`.
- [ ] Verification gate:
  - [ ] Confirm no remaining case-conflicting top-level paths.

## Workstream 3: Flatten `python/` into repository root

- [ ] Move these from `python/` to root:
  - [ ] `src/`
  - [ ] `tests/`
  - [ ] `tools/`
  - [ ] `docs/`
  - [ ] `game_data/`
  - [ ] `runs/`
  - [ ] `pyproject.toml`
  - [ ] `.gitignore` entries (merge safely with root ignore policy)
  - [ ] `README.md` content (merge/replace with root readme strategy)
- [ ] Remove now-empty `python/` directory and stale references.
- [ ] Update path-sensitive code/docs/tool defaults to root layout.
- [ ] Verification gate:
  - [ ] Run release verifier from root layout.
  - [ ] Run full unit + integration matrices.

## Workstream 4: Remove original game-data directories

- [ ] Remove legacy asset dirs from root:
  - [ ] `EFPS/`
  - [ ] `FNTS/`
  - [ ] `LEVS/`
  - [ ] `MUSIC/`
  - [ ] `WAVS/`
- [ ] Remove other redundant root-level data files only if no runtime/tool dependency remains.
- [ ] Verification gate:
  - [ ] Confirm startup and gameplay run with root `game_data/` only.
  - [ ] Run release verifier default mode.

## Workstream 5: Finalize docs and release handoff

- [ ] Update references from `python/...` paths to root-relative paths across docs.
- [ ] Update milestone tracker and completion notes.
- [ ] Publish final post-flatten verification snapshot.

## Commit slicing plan

- [ ] Commit A: optional legacy-compare tooling/tests.
- [ ] Commit B: conflict resolution prep (`ARCHIVE` moves/removals).
- [ ] Commit C: root flatten move + path updates.
- [ ] Commit D: legacy game-data directory removal.
- [ ] Commit E: docs/handoff finalization.

## Progress log

- Archived original DOS-era payload and legacy data/code trees under `ARCHIVE/` to unblock case-insensitive root flattening (`SRC`/`src` and `LICENSE` collisions).
- Preserved Python runtime project under `python/` unchanged for the next flatten step.
- Post-archive verification snapshot: `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `181 passed`.
- Completed Workstream 1 legacy-optional hardening:
  - `python/tools/asset_manifest_report.py` now defaults to `python_only` mode and supports optional `--legacy-root` strict parity mode.
  - `python/tests/integration/test_real_data_parse.py` legacy parity test now runs only when `ULTIMATETK_LEGACY_COMPARE_ROOT` is set.
  - `python/tools/release_verification.py` now supports `--legacy-compare-root` and wires strict parity env/path only when requested.
- Workstream 1 verification snapshot:
  - `python3 python/tools/release_verification.py --skip-integration` -> manifest(default python-only) + `181 passed` unit matrix.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `47 passed, 1 skipped` (legacy compare test skipped by default).
  - `python3 python/tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` -> strict legacy parity mode integration matrix `48 passed`.

## Completion criteria

- [ ] Project runs from repository root without `python/` wrapper directory.
- [ ] Default verification bundle does not require legacy root asset folders.
- [ ] Original game-data directories are removed.
- [ ] Full unit/integration/release verification passes.
