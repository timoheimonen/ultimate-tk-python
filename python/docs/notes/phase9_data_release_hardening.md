# Phase 9: Data Colocation and Release Hardening (Kickoff)

This phase finalizes single-player release readiness by ensuring the Python port runs fully from `python/`-local runtime data paths with no dependency on legacy root-level DOS asset directories.

Current baseline already implemented:

- Phase 8 regression suite is complete with behavior/render golden checks and command bundles.
- Runtime asset loading already routes through `GamePaths` and repository adapters under `python/`.
- Parse/render/runtime integration suites pass against migrated data layout.

## Phase 9 goals

- Ensure all required runtime assets are colocated under `python/game_data/`.
- Eliminate or gate any remaining root-level legacy data path dependencies.
- Add explicit isolation checks proving startup/gameplay works with Python-local assets only.
- Harden release workflow expectations (artifact hygiene, launch commands, verification bundles).

## Workstreams

1. Asset inventory and colocation manifest hardening
   - Build/update required asset manifest for runtime-critical files.
   - Validate manifest against current `python/game_data/` contents.
   - Flag and close missing/duplicated/legacy-only dependencies.

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

- [ ] Produce/refresh Phase 9 asset manifest and gap list.
- [ ] Land first runtime-path isolation hardening slice.
- [ ] Land first isolation regression test slice.
- [ ] Publish release workflow verification notes.
- [ ] Re-run full verification matrix after each closed workstream.

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
- Runtime path resolution is hardened to Python-local assets for release execution.
- Isolation regression checks pass alongside the existing full suite.
- `python_refactor.md` and this note reflect Phase 9 closure and final release-readiness handoff.
