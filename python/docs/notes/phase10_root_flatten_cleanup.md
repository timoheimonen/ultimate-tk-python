# Phase 10: Root Flatten and Legacy Cleanup (Checklist Plan)

This checklist defines the execution order for moving the Python project from `python/` to repository root while making legacy asset comparison optional and removing original game-data folders.

## Preconditions

- [ ] Confirm current branch is clean.
- [ ] Confirm Phase 9 release verification bundle passes before any path moves.
- [ ] Record a baseline verification snapshot:
  - [ ] `python3 python/tools/release_verification.py`

## Workstream 1: Make legacy-compare optional

- [ ] Update `tests/integration/test_real_data_parse.py`:
  - [ ] Default mode passes without legacy root directories.
  - [ ] Legacy parity checks run only when explicit legacy-compare mode is enabled.
- [ ] Update `tools/asset_manifest_report.py`:
  - [ ] Default mode builds/validates from `game_data` only.
  - [ ] Optional strict compare mode accepts explicit `--legacy-root`.
- [ ] Update `tools/release_verification.py`:
  - [ ] Default release bundle does not require legacy roots.
  - [ ] Optional legacy compare switch/path is supported.
- [ ] Verification gate:
  - [ ] Run unit matrix.
  - [ ] Run integration matrix.
  - [ ] Run release verifier in default mode.

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

## Completion criteria

- [ ] Project runs from repository root without `python/` wrapper directory.
- [ ] Default verification bundle does not require legacy root asset folders.
- [ ] Original game-data directories are removed.
- [ ] Full unit/integration/release verification passes.
