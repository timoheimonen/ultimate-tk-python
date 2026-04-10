# Phase 6: UI and Progression Flow (Kickoff)

This phase extends the Python port from combat-loop parity into broader game-flow parity: menu interaction, level progression, and non-combat progression UI states.

Current baseline already implemented:

- Boot -> main-menu -> gameplay scene flow exists with deterministic scene transitions.
- Main menu now supports interactive `start`/`quit` selection with deterministic non-autostart input handling, while preserving the autostart shortcut for test/dev loops.
- Gameplay and game-over loop is stable, and game-over already returns to main menu.
- Session state fields (`episode_index`, `level_index`, `player_name`) are wired into progression transitions and persisted-session hooks (load/new/save profile path for headless/terminal workflows).

## Phase 6 goals

- Add interactive main-menu flow so gameplay start/exit paths are explicit and testable without autostart shortcuts.
- Add level/episode progression flow so session indices advance deterministically on completion.
- Add inter-level and end-of-run UI states so progression outcomes are visible and not only runtime-internal.
- Add persistence hooks for progression/session continuity where practical for headless and terminal workflows.
- Lock regression coverage for scene transitions and progression invariants so future UI work does not destabilize core flow.

## Workstreams

1. Main menu interaction and transition wiring (completed)
   - Implement actionable menu entries (at minimum: start game, quit).
   - Wire menu navigation/select input handling in non-autostart runs.
   - Keep autostart path available for test/dev loops without regressing manual flow.

2. Session progression state machine (completed)
   - Define level-complete criteria and deterministic transition timing.
   - Advance `session.level_index` on completion; handle missing-next-level fallback explicitly.
   - Define restart/retry behavior on death versus successful completion.

3. Inter-level and run-outcome UI states (completed)
   - Add level-complete summary/transition scene state.
   - Add terminal/run-complete state (episode end or content end fallback).
   - Expose key progression metadata through runtime fields for verification tooling.

4. Persistence and profile continuity hooks (completed)
   - Define minimal persisted session payload (player name, episode/level progression markers).
   - Add explicit load/new-session behavior entry points.
   - Keep machine-specific paths and secrets out of persisted artifacts.

5. Regression expansion and lock criteria (pending)
   - Add scene-flow unit tests for menu -> gameplay -> progression -> menu loops.
   - Add scripted headless integration scenarios for completion/death/progression transitions.
   - Lock Phase 5 combat/entity invariants while Phase 6 UI work is in flight.

## Progress log

- Started and completed Workstream 1 by replacing the main-menu scaffold with interactive flow in `python/src/ultimatetk/ui/main_menu_scene.py`:
  - Added deterministic menu selection state with explicit `start` and `quit` entries.
  - Added non-autostart menu input handling for navigation (`MOVE_FORWARD`/`MOVE_BACKWARD` and left/right/strafe variants) and confirmation (`SHOOT`/`TOGGLE_SHOP`/`NEXT_WEAPON`).
  - Kept autostart behavior intact for existing test/dev loops when `autostart_gameplay=True` and `autostart_enabled=True`.
- Added Workstream 1 scene-flow regression coverage in `python/tests/unit/test_scene_flow.py`:
  - `test_boot_to_menu_requires_manual_start_when_autostart_is_disabled`
  - `test_main_menu_quit_selection_sets_runtime_running_false`
  - `test_gameplay_death_returns_to_menu_and_manual_start_reenters_gameplay`
- Added scripted headless integration coverage in `python/tests/integration/test_headless_input_script_runtime.py`:
  - `test_scripted_main_menu_manual_start_enters_gameplay_without_autostart`
  - `test_scripted_main_menu_quit_selection_stops_run_without_core_quit_event`
- Defined initial Workstream 2 completion trigger baseline for implementation: treat level completion as `enemies_alive == 0` in gameplay runtime state, then advance `session.level_index` with explicit missing-next-level fallback.
- Completed initial Workstream 2 progression state machine in `python/src/ultimatetk/systems/gameplay_scene.py`:
  - Added deterministic level-complete trigger (`alive_enemy_count == 0`) for manual progression runs (`autostart_gameplay=False`) so existing autostart-heavy regression loops remain stable while progression wiring lands.
  - Added deterministic progression transitions: successful completion advances `session.level_index` and reloads gameplay; missing-next-level fallback resets `session.level_index` to `0` and returns to non-autostart main menu.
  - Preserved death/retry behavior separation: death path still routes through game-over -> main menu without level advancement.
- Added Workstream 2 scene-flow regression coverage in `python/tests/unit/test_scene_flow.py`:
  - `test_level_completion_advances_session_index_and_reloads_gameplay_when_progression_enabled`
  - `test_level_completion_fallback_returns_to_menu_when_next_level_is_missing`
  - `test_gameplay_death_does_not_advance_session_index_when_progression_enabled`
- Added scripted headless progression coverage in `python/tests/integration/test_headless_input_script_runtime.py`:
  - `test_scripted_level_completion_advances_session_index_for_manual_progression_flow`
- Completed Workstream 3 inter-level/run-outcome UI state wiring by adding dedicated progression scenes in `python/src/ultimatetk/ui/progression_scene.py`:
  - Added `LevelCompleteScene` with deterministic hold/confirm flow before loading the next level.
  - Added `RunCompleteScene` with deterministic hold/confirm flow before returning to non-autostart main menu.
  - Wired progression transitions in `python/src/ultimatetk/systems/gameplay_scene.py` so level-complete and content-end fallback now route through explicit scene states instead of immediate scene swaps.
- Added Workstream 3 progression metadata publication in runtime state for verification tooling:
  - Added `progression_event`, `progression_from_level_index`, `progression_to_level_index`, `progression_has_next_level`, and `progression_ticks_remaining` in `python/src/ultimatetk/core/state.py`.
  - Included progression metadata in periodic status logging in `python/src/ultimatetk/core/platform.py`.
- Expanded Workstream 3 regression coverage:
  - Unit scene-flow updates in `python/tests/unit/test_scene_flow.py` now assert `level_complete` and `run_complete` scene transitions plus runtime progression metadata.
  - Added scripted integration fallback coverage in `python/tests/integration/test_headless_input_script_runtime.py`:
    - `test_scripted_run_complete_fallback_returns_to_main_menu_with_reset_index`
- Completed Workstream 4 persistence/profile continuity hooks:
  - Added session profile persistence module `python/src/ultimatetk/core/session_store.py` with minimal payload fields only (`player_name`, `episode_index`, `level_index`, plus schema `version`) persisted to `python/runs/profiles/session.json`.
  - Added explicit runtime entry points via CLI flags in `python/src/ultimatetk/__main__.py`:
    - `--load-session` to load persisted profile at startup,
    - `--new-session` to reset profile at startup,
    - `--no-save-session` to disable shutdown persistence.
  - Wired startup load/new behavior and shutdown auto-save hooks in `python/src/ultimatetk/core/app.py`.
  - Added persistence regression coverage:
    - `python/tests/unit/test_session_store.py`
    - `python/tests/unit/test_app_session_persistence.py`
    - `python/tests/unit/test_cli_session_args.py`
- Verification runs after Workstreams 1-3:
  - `python3 -m pytest tests/unit/test_scene_flow.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py -k "main_menu or level_completion or run_complete"`
  - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Additional verification runs after Workstream 4:
  - `python3 -m pytest tests/unit/test_session_store.py tests/unit/test_app_session_persistence.py tests/unit/test_cli_session_args.py`

## Kickoff checklist

- [x] Confirm initial Phase 6 target UX path (menu start + quit + level advance).
- [x] Define first minimal completion trigger for level progression path.
- [x] Implement Workstream 1 with unit scene-flow coverage.
- [x] Implement initial Workstream 2 progression advancement + fallback behavior.
- [x] Add at least one scripted integration progression scenario before broader UI polish.

## Verification plan

- Unit suites:
  - `python/tests/unit/test_scene_flow.py`
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_combat.py` (Phase 5 lock guard)
- Integration suite:
  - `python/tests/integration/test_headless_input_script_runtime.py`
- Phase verification command set:
  - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`

## Completion criteria

- Interactive non-autostart menu flow is implemented and verified.
- Session progression advances deterministically across at least one level-complete path.
- Run-outcome/inter-level UI states are present and test-covered.
- Phase 5 lock invariants remain passing while Phase 6 changes land.
- `python_refactor.md` and this note are kept current through each completed Phase 6 workstream.
