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

- [ ] Add runtime state fields for latest frame payload used by visual backends:
  - [ ] frame width/height (`320x200` expected)
  - [ ] indexed pixel bytes
  - [ ] palette bytes (VGA 6-bit channels)
- [ ] Keep existing digest/telemetry behavior unchanged for regression stability.
- [ ] Publish the frame payload at end of gameplay scene render.

Acceptance checks:

- [ ] Existing render digest tests continue passing unchanged.
- [ ] New state fields are updated every render frame in gameplay scene.

## Workstream 3: Implement pygame backend

- [ ] Add `PygamePlatformBackend` implementing `PlatformBackend` protocol.
- [ ] Startup responsibilities:
  - [ ] init pygame and display
  - [ ] choose window size using integer scale: `display = (320 * scale, 200 * scale)`
  - [ ] default scale `3`, allow explicit scale values
- [ ] Present responsibilities:
  - [ ] convert indexed frame + palette to RGB surface
  - [ ] draw scaled surface to window with nearest-neighbor behavior
  - [ ] update display each frame
- [ ] Poll responsibilities:
  - [ ] map keyboard press/release to existing `InputAction` events
  - [ ] map quit/window-close to `QUIT`
  - [ ] support direct weapon slot keys
- [ ] Shutdown responsibilities:
  - [ ] graceful `pygame.quit()` with no impact on headless/terminal paths

Acceptance checks:

- [ ] Interactive run opens a window and presents animated frames.
- [ ] Close button and `Esc` both trigger clean shutdown.
- [ ] Keyboard control parity with terminal backend is functionally equivalent.

## Workstream 4: Scaling policy and CLI controls

- [ ] Add CLI/runtime config for pygame scale (integer, min `1`).
- [ ] Validate and clamp/reject invalid values.
- [ ] Document recommended scales:
  - [ ] `--window-scale 2` -> `640x400`
  - [ ] `--window-scale 3` -> `960x600`

Acceptance checks:

- [ ] Default pygame launch uses `960x600`.
- [ ] Explicit `--window-scale 2` launches `640x400`.
- [ ] Non-integer/invalid scale fails fast with clear message.

## Workstream 5: Packaging, tests, and docs

- [ ] Add optional dependency group for pygame in `pyproject.toml`.
- [ ] Add unit tests for:
  - [ ] platform selection (`headless`, `terminal`, `pygame`)
  - [ ] CLI argument parsing for pygame scale
  - [ ] lazy import/missing dependency behavior
  - [ ] pygame input mapping logic (event translation unit-tested without real display)
- [ ] Update `README.md` with pygame run examples and scaling notes.
- [ ] Update `python_refactor.md` with Phase 11 kickoff/status line.

Acceptance checks:

- [ ] Existing unit/integration suites remain green in non-pygame environments.
- [ ] Pygame-specific tests are deterministic and skip safely when dependency is unavailable.

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
- Verification snapshot:
  - `python3 -m pytest tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `10 passed`.
  - `PYTHONPATH=src python3 -m ultimatetk --max-seconds 0.1` -> headless smoke run passed.
  - `PYTHONPATH=src python3 -m ultimatetk --platform pygame --max-seconds 0.01` -> expected fail-fast with clear missing-pygame install hint.
