# Phase 11: Optional Pygame Runtime Frontend (Plan)

This phase adds an interactive graphics window while preserving the existing deterministic headless and terminal workflows.

The key constraints for this phase are:

- `pygame` must only be imported/used when explicitly selected at runtime.
- Default runtime behavior must remain headless-first and release-verifier safe.
- Internal render resolution stays `320x200`; display output uses integer upscaling (target `x2`/`x3`).

## Goals

- Add a new `pygame` platform backend without changing existing headless simulation semantics.
- Keep `pygame` as an optional dependency so CI/release workflows do not require SDL/graphics packages.
- Reuse the current software renderer output (indexed pixels + palette) for on-screen presentation.
- Preserve input action parity across terminal and pygame backends.

## Non-goals (this phase)

- No gameplay logic rewrite for pygame-specific rendering paths.
- No AI training interface integration yet (only leave runtime hooks compatible with later integration).
- No change to canonical internal render size (`320x200`).

## Workstream 1: Runtime selection and lazy pygame import

- [x] Extend runtime platform choices to include `pygame` in CLI/config.
- [x] Keep default platform as `headless`.
- [x] Ensure pygame module import is lazy and only executed when `--platform pygame` is selected.
- [x] Provide a clear runtime error when pygame backend is requested but dependency is missing.

Acceptance checks:

- [x] `PYTHONPATH=src python3 -m ultimatetk --max-seconds 0.1` still runs with no pygame import requirement.
- [x] `PYTHONPATH=src python3 -m ultimatetk --platform pygame ...` attempts pygame backend creation.
- [x] Missing pygame dependency yields actionable install hint.

## Workstream 2: Frame handoff for visual backend presentation

- [x] Add runtime state fields for latest frame payload used by visual backends:
  - [x] frame width/height (`320x200` expected)
  - [x] indexed pixel bytes
  - [x] palette bytes (VGA 6-bit channels)
- [x] Keep existing digest/telemetry behavior unchanged for regression stability.
- [x] Publish the frame payload at end of gameplay scene render.

Acceptance checks:

- [x] Existing render digest tests continue passing unchanged.
- [x] New state fields are updated every render frame in gameplay scene.

## Workstream 3: Implement pygame backend

- [x] Add `PygamePlatformBackend` implementing `PlatformBackend` protocol.
- [x] Startup responsibilities:
  - [x] init pygame and display
  - [x] choose window size using integer scale: `display = (320 * scale, 200 * scale)`
  - [x] default scale `3`, allow explicit scale values
- [x] Present responsibilities:
  - [x] convert indexed frame + palette to RGB surface
  - [x] draw scaled surface to window with nearest-neighbor behavior
  - [x] update display each frame
- [x] Poll responsibilities:
  - [x] map keyboard press/release to existing `InputAction` events
  - [x] map quit/window-close to `QUIT`
  - [x] support direct weapon slot keys
- [x] Shutdown responsibilities:
  - [x] graceful `pygame.quit()` with no impact on headless/terminal paths

Acceptance checks:

- [ ] Interactive run opens a window and presents animated frames.
- [ ] Close button and `Esc` both trigger clean shutdown.
- [ ] Keyboard control parity with terminal backend is functionally equivalent.

## Workstream 4: Scaling policy and CLI controls

- [x] Add CLI/runtime config for pygame scale (integer, min `1`).
- [x] Validate and clamp/reject invalid values.
- [x] Document recommended scales:
  - [x] `--window-scale 2` -> `640x400`
  - [x] `--window-scale 3` -> `960x600`

Acceptance checks:

- [ ] Default pygame launch uses `960x600`.
- [ ] Explicit `--window-scale 2` launches `640x400`.
- [ ] Non-integer/invalid scale fails fast with clear message.

## Workstream 5: Packaging, tests, and docs

- [x] Add optional dependency group for pygame in `pyproject.toml`.
- [x] Add unit tests for:
  - [x] platform selection (`headless`, `terminal`, `pygame`)
  - [x] CLI argument parsing for pygame scale
  - [x] lazy import/missing dependency behavior
  - [x] pygame input mapping logic (event translation unit-tested without real display)
- [x] Update `README.md` with pygame run examples and scaling notes.
- [x] Update `python_refactor.md` with Phase 11 kickoff/status line.

Acceptance checks:

- [x] Existing unit/integration suites remain green in non-pygame environments.
- [x] Pygame-specific tests are deterministic and dependency-safe when pygame is unavailable.

## Verification matrix

- Core regression bundle (must stay green):
  - `python3 tools/release_verification.py`
- Focused platform/CLI tests:
  - `python3 -m pytest tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py`
- New pygame-focused unit slice:
  - `python3 -m pytest tests/unit/test_pygame_platform.py`

## Commit slicing plan

- [ ] Commit A (`feat`): add runtime/CLI pygame selection and lazy import guardrails.
- [ ] Commit B (`feat`): publish render frame payload in runtime state.
- [ ] Commit C (`feat`): implement pygame backend (window, present, input, shutdown).
- [ ] Commit D (`test`): add pygame/CLI/platform unit coverage.
- [ ] Commit E (`docs`): update README + tracker + phase note progress/closeout.

## Completion criteria

- [ ] Game runs in pygame mode only when explicitly requested.
- [ ] Default headless and release verification flow do not require pygame.
- [ ] Pygame window displays `320x200` content at integer scale (`x2`/`x3` supported).
- [ ] Input controls, quit handling, and frame presentation are stable.
- [ ] Docs and milestone tracking reflect Phase 11 status.

## Progress log

- Completed Workstream 1 runtime selection/lazy-import slice:
  - Added `pygame` platform CLI selection and runtime backend wiring.
  - Added `PygamePlatformBackend` startup lazy import guard (`importlib.import_module("pygame")` only in pygame backend startup path).
  - Added explicit runtime error message with install hint when pygame is missing.
- Added focused unit coverage for platform selection, CLI parse acceptance, and pygame missing-dependency startup behavior.
- Completed Workstream 2 frame-payload publication slice:
  - Added runtime render payload fields in `RuntimeState` (`last_render_pixels`, `last_render_palette`).
  - Gameplay render now publishes indexed frame payload + palette while preserving digest/width/height telemetry.
  - Added scene-flow assertions that payload dimensions and sizes are populated during gameplay rendering.
- Completed Workstream 3 backend implementation slice:
  - Replaced pygame backend stub with startup/poll/present/shutdown runtime flow.
  - Added keyboard/action parity mapping (press/release, quit, and direct weapon-slot keys).
  - Added present-time indexed-frame conversion and integer-scaled blit path.
  - Added unit coverage for poll-event mapping and frame presentation behavior with mocked pygame module.
- Completed Workstream 4 scaling/CLI slice:
  - Added `--window-scale` CLI flag with positive-integer validation.
  - Added runtime config wiring (`pygame_window_scale`) and application-level validation.
  - Pygame backend now receives configured scale from runtime config.
  - Added CLI/app unit coverage for explicit scale, defaults, and invalid value rejection.
- Completed Workstream 5 packaging/tests/docs slice:
  - Added optional dependency extra `pygame` in `pyproject.toml`.
  - Updated `README.md` with pygame launch command, optional install command, and scale examples.
  - Updated milestone tracker entries in `python_refactor.md`.
  - Re-ran full release verification matrix to ensure non-pygame workflows remain green.
- Verification snapshot:
  - `python3 -m pytest tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `10 passed`.
  - `python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `52 passed`.
  - `python3 tools/release_verification.py` -> unit `181 passed`, integration `47 passed, 1 skipped`.
  - `PYTHONPATH=src python3 -m ultimatetk --max-seconds 0.1` -> headless smoke run passed.
  - `PYTHONPATH=src python3 -m ultimatetk --platform pygame --max-seconds 0.01` -> expected fail-fast with clear missing-pygame install hint.
  - `PYTHONPATH=src python3 -m ultimatetk --platform pygame --window-scale 2 --max-seconds 0.01` -> expected fail-fast with clear missing-pygame install hint (scale arg path exercised).
