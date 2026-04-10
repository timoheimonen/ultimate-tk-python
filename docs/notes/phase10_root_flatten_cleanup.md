# Phase 10: Root Flatten and Legacy Cleanup (Completed)

This checklist defines the execution order for root-level Python layout hardening, optional legacy parity checks, and legacy game-data cleanup.

Note: older phase notes may still reference `python/...` paths as historical context from pre-flatten commits.

## Preconditions

- [ ] Confirm current branch is clean.
- [ ] Confirm Phase 9 release verification bundle passes before any path moves.
- [ ] Record a baseline verification snapshot:
  - [ ] `python3 tools/release_verification.py`

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
  - [x] Run unit matrix (`181 passed`).
  - [x] Run integration matrix (`47 passed, 1 skipped` default mode).
  - [x] Run release verifier in default mode.

## Workstream 2: Resolve root-level name conflicts

- [x] Inventory root paths that conflict with Python-root layout on case-insensitive filesystems:
  - [x] `SRC/` vs future `src/`
  - [x] `LICENSE` vs `python/LICENSE`
- [x] Choose destination for retained legacy code/binaries:
  - [x] Move to `ARCHIVE/`.
- [x] Verification gate:
  - [x] Confirm no remaining case-conflicting top-level paths.

## Workstream 3: Flatten `python/` into repository root

- [x] Move these from `python/` to root:
  - [x] `src/`
  - [x] `tests/`
  - [x] `tools/`
  - [x] `docs/`
  - [x] `game_data/`
  - [x] `runs/`
  - [x] `pyproject.toml`
  - [x] `.gitignore` entries (merge safely with root ignore policy)
  - [x] `README.md` content (merge/replace with root readme strategy)
- [x] Remove now-empty `python/` directory and stale references.
- [x] Update path-sensitive code/docs/tool defaults to root layout.
- [x] Verification gate:
  - [x] Run release verifier from root layout.
  - [x] Run full unit + integration matrices.

## Workstream 4: Remove original game-data directories

- [x] Remove legacy asset dirs from root:
  - [x] `EFPS/`
  - [x] `FNTS/`
  - [x] `LEVS/`
  - [x] `MUSIC/`
  - [x] `WAVS/`
- [x] Remove other redundant root-level data files only if no runtime/tool dependency remains.
- [x] Verification gate:
  - [x] Confirm startup and gameplay run with root `game_data/` only.
  - [x] Run release verifier default mode.

## Workstream 5: Finalize docs and release handoff

- [x] Update references from `python/...` paths to root-relative paths across docs.
- [x] Update milestone tracker and completion notes.
- [x] Publish final post-flatten verification snapshot.

## Commit slicing plan

- [x] Commit A: optional legacy-compare tooling/tests.
- [x] Commit B: conflict resolution prep (`ARCHIVE` moves/removals).
- [x] Commit C: root flatten move + path updates.
- [x] Commit D: legacy game-data directory removal.
- [x] Commit E: docs/handoff finalization.

## Progress log

- Archived original DOS-era payload and legacy data/code trees under `ARCHIVE/` to unblock case-insensitive root flattening (`SRC`/`src` and `LICENSE` collisions).
- Post-archive verification snapshot: `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `181 passed`.
- Completed Workstream 1 legacy-optional hardening:
  - `tools/asset_manifest_report.py` now defaults to `python_only` mode and supports optional `--legacy-root` strict parity mode.
  - `tests/integration/test_real_data_parse.py` legacy parity test now runs only when `ULTIMATETK_LEGACY_COMPARE_ROOT` is set.
  - `tools/release_verification.py` now supports `--legacy-compare-root` and wires strict parity env/path only when requested.
- Workstream 1 verification snapshot:
  - `python3 tools/release_verification.py --skip-integration` -> manifest(default python-only) + `181 passed` unit matrix.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `47 passed, 1 skipped` (legacy compare test skipped by default).
  - `python3 tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` -> strict legacy parity mode integration matrix `48 passed`.
- Completed Workstream 3 root flatten:
  - Moved `src/`, `tests/`, `tools/`, `docs/`, `game_data/`, `runs/`, `pyproject.toml`, `.gitignore`, and `README.md` from `python/` to repository root.
  - Removed the now-empty `python/` wrapper directory.
  - Updated tooling/docs path defaults and commands for root layout.
- Workstream 3 verification snapshot:
  - `python3 tools/release_verification.py --skip-integration` -> `181 passed` unit matrix.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `47 passed, 1 skipped`.
  - `python3 tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` -> strict parity integration matrix `48 passed`.
- Completed Workstream 4 root cleanup:
  - Original root legacy asset directories remain archived under `ARCHIVE/` and are no longer present at root.
  - Redundant root-level legacy data files (`OPTIONS.CFG`, `PALETTE.TAB`) were also archived under `ARCHIVE/`.
- Final verification snapshot (post-flatten/post-cleanup):
  - `python3 tools/release_verification.py` -> `181 passed`, integration `47 passed, 1 skipped` (default mode; legacy compare optional).
  - `python3 tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` -> strict parity integration matrix `48 passed`.

## Completion criteria

- [x] Project runs from repository root without `python/` wrapper directory.
- [x] Default verification bundle does not require legacy root asset folders.
- [x] Original game-data directories are removed.
- [x] Full unit/integration/release verification passes.

## Phase 10 closeout

- Phase 10 workstreams are complete.
- Runtime/project layout is root-native (`src/`, `tests/`, `tools/`, `docs/`, `game_data/`, `runs/`).
- Legacy payload is archived under `ARCHIVE/`, with optional strict parity checks still available.
