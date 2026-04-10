# Phase 9: Data Colocation and Release Hardening (Kickoff)

This phase finalizes single-player release readiness by ensuring the Python port runs fully from `python/`-local runtime data paths with no dependency on legacy root-level DOS asset directories.

Current baseline already implemented:

- Phase 8 regression suite is complete with behavior/render golden checks and command bundles.
- Runtime asset loading already routes through `GamePaths` and repository adapters under `python/`.
- Parse/render/runtime integration suites pass against migrated data layout.

## Phase 9 goals

- Ensure all required runtime assets are colocated under `python/game_data/`.
- Ensure all graphical (`EFPS/`, `FNTS/`) and sound (`MUSIC/`, `WAVS/`) assets can be read from original legacy sources into `python/game_data/` with no migration gaps.
- Eliminate or gate any remaining root-level legacy data path dependencies.
- Add explicit isolation checks proving startup/gameplay works with Python-local assets only.
- Harden release workflow expectations (artifact hygiene, launch commands, verification bundles).

## Workstreams

1. Asset inventory and colocation manifest hardening
   - Build/update required asset manifest for runtime-critical files.
   - Validate manifest against current `python/game_data/` contents.
   - Validate graphical/sound asset parity from original legacy source directories into `python/game_data/`.
   - Flag and close missing/duplicated/legacy-only dependencies.

## Workstream 1 slice: asset manifest + gap lock

- Added `python/tools/asset_manifest_report.py` to generate a deterministic manifest and gap report from legacy root assets into `python/game_data/`.
- Generated and checked in:
  - `python/game_data/asset_manifest.json`
  - `python/game_data/asset_manifest_gap_list.md`
- Current gap report status:
  - `EFPS`, `FNTS`, `LEVS`, `MUSIC`, `WAVS` all show `missing=0` and `extra=0`.
  - `PALETTE.TAB` present as required; `OPTIONS.CFG` present as optional.
- Added missing-asset regression locks in `python/tests/integration/test_real_data_parse.py`:
  - manifest required-file existence check under `python/game_data/`
  - graphical/sound parity check against original legacy source directories

2. Runtime path isolation hardening
    - Audit loaders/resolvers for fallback paths that could read root-level legacy directories.
    - Restrict path resolution to Python-local data roots for release mode.
    - Preserve developer diagnostics without weakening release isolation guarantees.

3. Isolation regression coverage
   - Add integration checks that exercise startup/render/gameplay using only Python-local assets.
   - Add negative checks for missing-required-assets behavior where practical.
   - Keep regression deterministic and CI-friendly.

4. Release workflow and docs hardening
   - Document release verification command bundles.
   - Document runtime artifact expectations (`python/runs/`, logs, profiles, screenshots).
   - Ensure machine-specific and secret-bearing artifacts remain excluded from commits.

5. Phase closeout and final handoff
   - Re-run full verification matrix under hardened path assumptions.
   - Confirm milestones and docs reflect final single-player release-ready state.
   - Update `python_refactor.md` and phase notes with completion summary.

## Kickoff checklist

- [x] Produce/refresh Phase 9 asset manifest and gap list.
- [x] Land first runtime-path isolation hardening slice.
- [x] Land first isolation regression test slice.
- [ ] Publish release workflow verification notes.
- [ ] Re-run full verification matrix after each closed workstream.

## Progress log

- Started and completed first Phase 9 Workstream 1 slice by adding a generated asset manifest + gap list workflow under `python/game_data/`.
- Locked missing-asset checks for manifest-required files and for graphical/sound parity from original legacy directories into `python/game_data/`.
- Verification snapshot after Workstream 1 slice:
  - `python3 -m pytest tests/integration/test_real_data_parse.py` -> `3 passed`.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `47 passed`.
- Completed first Phase 9 Workstream 2 runtime-isolation hardening slice:
  - `GameApplication.create` now enforces manifest-backed required-asset validation via `GamePaths.validate_game_data_layout(enforce_manifest=True)`.
  - Added strict `asset_manifest.json` validation in `GamePaths` (manifest required, non-empty required file list, in-root path enforcement, missing-file fail-fast).
  - Added repository path-isolation guard in `_resolve_case_insensitive` to reject symlink/path escapes outside expected asset directories.
- Completed first Phase 9 Workstream 3 isolation regression slice:
  - Added negative-path integration lock asserting startup fails fast when a manifest-required asset is missing.
  - Added unit lock assertions for case-insensitive local file resolution and symlink-escape rejection in asset repository resolution.
- Updated verification snapshot after Workstream 2/3 slices:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `181 passed`.
  - `python3 -m pytest tests/unit/test_asset_repository.py tests/unit/test_app_session_persistence.py tests/integration/test_real_data_parse.py` -> `10 passed`.
  - `python3 -m pytest tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py` -> `6 passed`.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `48 passed`.

## Verification plan

- Unit/scene-flow suites:
  - `python/tests/unit/test_fixed_step_clock.py`
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_combat.py`
  - `python/tests/unit/test_scene_flow.py`
- Integration suites:
  - `python/tests/integration/test_headless_input_script_runtime.py`
  - `python/tests/integration/test_real_data_render.py`
  - `python/tests/integration/test_real_data_parse.py`
- Phase verification command set:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py`

## Completion criteria

- Required runtime data is fully colocated under `python/game_data/` for release scope.
- All graphical and sound assets are verifiably readable/migrated from original legacy source directories into `python/game_data/` with no manifest gaps.
- Runtime path resolution is hardened to Python-local assets for release execution.
- Isolation regression checks pass alongside the existing full suite.
- `python_refactor.md` and this note reflect Phase 9 closure and final release-readiness handoff.
