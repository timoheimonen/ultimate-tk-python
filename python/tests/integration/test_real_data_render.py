from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.paths import GamePaths
from ultimatetk.rendering import RenderFlags, SoftwareRenderer, camera_from_player_start, frame_digest


_LEVEL1_CAMERA_X = 90
_LEVEL1_CAMERA_Y = 90
_LEVEL1_WITH_EFFECTS_DIGEST = 2613501106
_LEVEL1_WITHOUT_EFFECTS_DIGEST = 2826512403


class RealDataRenderTests(unittest.TestCase):
    def test_render_known_level_frame(self) -> None:
        paths = GamePaths.discover()
        if not (paths.game_data_root / "palette.tab").exists():
            self.skipTest("python/game_data not migrated yet")

        repo = GameDataRepository(paths)
        level = repo.load_lev("LEVEL1.LEV", episode="DEFAULT")
        renderer = SoftwareRenderer.from_assets(
            level=level,
            floor_image=repo.load_efp("FLOOR1.EFP"),
            wall_image=repo.load_efp("WALLS1.EFP"),
            shadow_image=repo.load_efp("SHADOWS.EFP"),
            palette_tables=repo.load_palette_tables(),
        )

        camera_x, camera_y = camera_from_player_start(level)
        with_effects = renderer.render(
            camera_x=camera_x,
            camera_y=camera_y,
            flags=RenderFlags(dark_mode=True, light_effects=True, shadows=True),
            spot_phase_degrees=120,
        )
        without_effects = renderer.render(
            camera_x=camera_x,
            camera_y=camera_y,
            flags=RenderFlags(dark_mode=False, light_effects=False, shadows=False),
            spot_phase_degrees=120,
        )

        self.assertEqual(camera_x, _LEVEL1_CAMERA_X)
        self.assertEqual(camera_y, _LEVEL1_CAMERA_Y)
        self.assertEqual(len(with_effects), 320 * 200)
        self.assertGreater(len(set(with_effects)), 20)
        self.assertEqual(frame_digest(with_effects), _LEVEL1_WITH_EFFECTS_DIGEST)
        self.assertEqual(frame_digest(without_effects), _LEVEL1_WITHOUT_EFFECTS_DIGEST)
        self.assertNotEqual(with_effects, without_effects)


if __name__ == "__main__":
    unittest.main()
