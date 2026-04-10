from __future__ import annotations

import argparse
from pathlib import Path
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.paths import GamePaths
from ultimatetk.rendering import (
    RenderFlags,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SoftwareRenderer,
    WorldSprite,
    camera_from_player_start,
    extract_horizontal_sprite_frame,
    frame_digest,
    write_indexed_ppm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a baseline gameplay frame to PPM")
    parser.add_argument("--episode", default="DEFAULT", help="Episode directory in game_data/levs")
    parser.add_argument("--lev", default="LEVEL1.LEV", help="Level filename inside episode")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "runs" / "screenshots" / "phase3_render_probe.ppm",
        help="Output .ppm file path",
    )
    parser.add_argument("--spot-phase", type=int, default=120, help="Spot light sine phase in degrees")
    parser.add_argument("--camera-x", type=int, default=None, help="Override camera X in world pixels")
    parser.add_argument("--camera-y", type=int, default=None, help="Override camera Y in world pixels")
    parser.add_argument("--disable-dark-mode", action="store_true", help="Disable dark floor mode")
    parser.add_argument("--disable-lights", action="store_true", help="Disable spot light rendering")
    parser.add_argument("--disable-shadows", action="store_true", help="Disable block shadow rendering")
    return parser.parse_args()


def _load_demo_sprites(repo: GameDataRepository, spawn_x: int, spawn_y: int) -> tuple[WorldSprite, ...]:
    sprites: list[WorldSprite] = []

    try:
        crate_sheet = repo.load_efp("CRATES.EFP")
        crate_frame = extract_horizontal_sprite_frame(
            crate_sheet,
            frame_width=14,
            frame_height=14,
            frame_index=0,
        )
        sprites.append(
            WorldSprite(
                world_x=spawn_x + 20,
                world_y=spawn_y + 10,
                width=14,
                height=14,
                pixels=crate_frame,
                anchor_x=7,
                anchor_y=7,
            ),
        )
    except (FileNotFoundError, ValueError):
        pass

    try:
        target = repo.load_efp("TARGET.EFP")
        sprites.append(
            WorldSprite(
                world_x=spawn_x,
                world_y=spawn_y,
                width=target.width,
                height=target.height,
                pixels=target.pixels,
                anchor_x=target.width // 2,
                anchor_y=target.height // 2,
                translucent=True,
            ),
        )
    except FileNotFoundError:
        pass

    return tuple(sprites)


def main() -> int:
    args = parse_args()

    paths = GamePaths.discover()
    paths.validate_game_data_layout()
    repo = GameDataRepository(paths)

    level = repo.load_lev(args.lev, episode=args.episode)
    renderer = SoftwareRenderer.from_assets(
        level=level,
        floor_image=repo.load_efp("FLOOR1.EFP"),
        wall_image=repo.load_efp("WALLS1.EFP"),
        shadow_image=repo.load_efp("SHADOWS.EFP"),
        palette_tables=repo.load_palette_tables(),
    )

    options = repo.try_load_options()
    if options is None:
        flags = RenderFlags()
    else:
        flags = RenderFlags(
            dark_mode=bool(options.dark_mode),
            light_effects=bool(options.light_effects),
            shadows=bool(options.shadows),
        )

    if args.disable_dark_mode:
        flags = RenderFlags(
            dark_mode=False,
            light_effects=flags.light_effects,
            shadows=flags.shadows,
        )
    if args.disable_lights:
        flags = RenderFlags(
            dark_mode=flags.dark_mode,
            light_effects=False,
            shadows=flags.shadows,
        )
    if args.disable_shadows:
        flags = RenderFlags(
            dark_mode=flags.dark_mode,
            light_effects=flags.light_effects,
            shadows=False,
        )

    if args.camera_x is None or args.camera_y is None:
        camera_x, camera_y = camera_from_player_start(level)
    else:
        camera_x, camera_y = args.camera_x, args.camera_y
    camera_x, camera_y = renderer.clamp_camera(camera_x, camera_y)

    spawn_x = level.player_start_x[0] * 20 + 14
    spawn_y = level.player_start_y[0] * 20 + 14
    sprites = _load_demo_sprites(repo, spawn_x=spawn_x, spawn_y=spawn_y)

    pixels = renderer.render(
        camera_x=camera_x,
        camera_y=camera_y,
        flags=flags,
        spot_phase_degrees=args.spot_phase,
        sprites=sprites,
    )

    write_indexed_ppm(
        args.output,
        pixels,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        renderer.palette_bytes,
    )

    digest = frame_digest(pixels)
    print(f"rendered: {args.episode}/{args.lev}")
    print(f"camera: {camera_x},{camera_y}")
    print(
        "flags: "
        f"dark={flags.dark_mode} lights={flags.light_effects} shadows={flags.shadows}",
    )
    print(f"output: {args.output}")
    print(f"digest: {digest:08x}")
    print(f"unique_colors: {len(set(pixels))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
