# Pygame Backend Plan

## Goal
Add an optional graphical window backend using `pygame` that presents the existing software-rendered frame buffer and maps keyboard input into the current event model, without changing simulation logic.

## Scope
- In scope:
  - New runtime platform backend: `pygame`
  - Window creation, frame presentation, and keyboard input mapping
  - CLI/config support for selecting `--platform pygame`
  - Lazy/on-demand `pygame` import (only when backend is selected)
  - Tests for backend selection and input mapping helpers
  - Documentation for setup and run commands
- Out of scope (initially):
  - Menu/UI redesign for window usage
  - Pixel shader/filter post-processing
  - Gamepad support
  - Gymnasium rendering dependencies

## Design Principles
- Keep backend isolated from gameplay systems.
- Keep deterministic simulation path unchanged.
- Keep `pygame` optional for users running headless/terminal/CI.
- Reuse existing `AppEvent` and `InputAction` semantics.

## Architecture

### 1) Platform Selection and Config
Update runtime platform selection to accept `pygame`.

Files:
- `python/src/ultimatetk/__main__.py`
- `python/src/ultimatetk/core/config.py`
- `python/src/ultimatetk/core/app.py`

Planned additions:
- CLI choice: `--platform pygame`
- Optional window args:
  - `--window-scale` (default `3`)
  - optional later: `--window-vsync`, `--window-title`

### 2) Pygame Platform Backend
Add `PygamePlatformBackend` implementing the existing `PlatformBackend` protocol.

Suggested path:
- `python/src/ultimatetk/core/platform_pygame.py`

Responsibilities:
- `startup(context)`:
  - lazy import `pygame` (`try/except ImportError`)
  - initialize pygame and create window
  - initialize key mapping and held state tracking
- `poll_events()`:
  - convert pygame events to `AppEvent`s
  - handle `QUIT` and `ESC`
- `present(context, scene_name, alpha)`:
  - read last rendered frame payload from runtime state
  - convert indexed pixels to RGB and blit to window
  - nearest-neighbor scaling to preserve pixel look
  - `flip()`/`update()` display
- `shutdown(context)`:
  - release pygame resources cleanly

### 3) Render Payload Hand-off
Current gameplay render stores digest/size metadata only. Add runtime payload fields so platform backends can present images.

File:
- `python/src/ultimatetk/core/state.py`

Planned runtime additions:
- `last_render_pixels: bytes = b""` (indexed 8-bit frame, 320x200)
- `last_render_palette: bytes = b""` (768 bytes RGB palette)

Publishing points:
- `python/src/ultimatetk/systems/gameplay_scene.py`
  - after frame generation, publish pixels + palette
- non-gameplay scenes can publish empty payload or simple placeholder frame

### 4) Input Mapping (Pygame -> AppEvent)
Map keyboard input to existing actions used by terminal backend for parity.

Action map targets:
- movement/turn/strafe/shoot
- weapon cycle/direct selection
- shop toggle and navigation-related actions
- quit via window close or `ESC`

Implementation detail:
- factor mapping into pure helper functions for easy unit testing
- track key held state to emit press/release events correctly

### 5) Palette Conversion and Blitting
Rendering pipeline remains indexed color; backend performs present-time conversion.

Plan:
- build 256-color RGB lookup from palette bytes
- convert indexed frame to RGB byte buffer each frame
- blit to base surface (320x200)
- scale to display resolution (`320*scale`, `200*scale`) with nearest filter

Performance notes:
- keep conversion path straightforward for v1
- optimize only if profiling shows present-time bottleneck

## Lazy Import Strategy (Required)
`pygame` must be imported only on demand.

Rules:
- do not import `pygame` at module top level in shared runtime modules
- only import in `PygamePlatformBackend` startup path (or constructor guarded by platform choice)
- if missing, raise clear actionable error:
  - "pygame backend requested but pygame is not installed; install with `pip install pygame`"

## Testing Plan

### Unit
- Extend platform selection tests:
  - `python/tests/unit/test_app_platform_selection.py`
  - assert `RuntimeConfig(platform="pygame")` selects pygame backend
- Add pygame mapping tests (pure helper tests, no real window required):
  - keydown/keyup -> action pressed/released
  - quit event mapping
  - weapon select keys

### Integration/Smoke
- Existing full test suite must remain green in non-pygame modes.
- Optional local smoke command:
  - `PYTHONPATH=src python3 -m ultimatetk --platform pygame --autostart-gameplay`

## Documentation Plan
Update:
- `python/README.md`
- `python/docs/notes/phase4_input_control.md`
- `python_refactor.md`

Include:
- install instruction for pygame
- graphical run command
- control reference and known limitations

## Risks and Mitigations
- Risk: coupling presentation logic into simulation
  - Mitigation: keep all window code inside platform backend
- Risk: optional dependency breaks CI
  - Mitigation: lazy import and tests that avoid hard pygame dependency
- Risk: input semantics diverge from terminal mode
  - Mitigation: shared action mapping constants and parity tests

## Implementation Phases

### Phase 1: Backend scaffold
- add `pygame` platform choice and backend class skeleton
- add lazy import and startup/shutdown structure

### Phase 2: Frame payload publication
- publish framebuffer payload in runtime state
- ensure no regressions for headless/terminal

### Phase 3: Window present path
- implement indexed->RGB conversion and nearest-neighbor scaling
- verify live gameplay display

### Phase 4: Input parity
- implement key mapping and held-action transitions
- validate controls against terminal behavior

### Phase 5: Tests and docs
- add/update unit tests and README/notes
- run full Python test suite

## Definition of Done (Pygame v1)
- `--platform pygame` opens a working game window.
- Keyboard control parity is acceptable vs terminal backend.
- `pygame` dependency remains optional and lazily loaded.
- Existing headless and terminal flows remain functional.
- Test suite passes and docs are updated.
