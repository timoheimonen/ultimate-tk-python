# Phase 3: Rendering Baseline

Implemented software rendering modules under `python/src/ultimatetk/rendering/`:

- `framebuffer.py`
  - Indexed 8-bit frame buffer with clipping and blit operations.
  - Supports opaque, transparent, and translucent sprite compositing.
- `software.py`
  - Gameplay-oriented renderer that draws floor/wall tiles from `.EFP` sheets.
  - Applies block shadows through `shadow_table` and spot lights through `normal_light_table`.
  - Builds dark floor tiles using the legacy luminance mapping formula.
- `palette.py`
  - Converts VGA 6-bit palette channels to RGB24 and writes indexed PPM screenshots.

Runtime integration:

- `python/src/ultimatetk/systems/gameplay_scene.py`
  - Loads level/graphics tables from `python/game_data/`.
  - Renders a baseline gameplay frame each tick in headless mode.
  - Publishes frame digest metadata into runtime state for logging.

Verification:

- Unit tests:
  - `python/tests/unit/test_render_framebuffer.py`
  - `python/tests/unit/test_software_renderer.py`
- Integration test:
  - `python/tests/integration/test_real_data_render.py`
- Probe tool:
  - `python/tools/render_probe.py` writes a sample frame to `runs/screenshots/*.ppm`.
