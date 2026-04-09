from __future__ import annotations

from typing import Sequence

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode
from ultimatetk.formats.efp import EfpImage
from ultimatetk.formats.lev import LevelData
from ultimatetk.rendering import (
    RenderFlags,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SoftwareRenderer,
    WorldSprite,
    extract_horizontal_sprite_frame,
    frame_digest,
)
from ultimatetk.systems.combat import (
    CRATE_SIZE,
    CrateState,
    EnemyProjectile,
    EnemyState,
    advance_crate_effects,
    advance_enemy_effects,
    alive_crate_count,
    alive_enemy_count,
    collect_crates_for_player,
    resolve_shot_against_enemies,
    spawn_crates_for_level,
    spawn_enemies_for_level,
    update_enemy_behavior,
    update_enemy_projectiles,
)
from ultimatetk.systems.player_control import (
    PLAYER_CENTER_OFFSET,
    PlayerState,
    aim_point_from_player,
    apply_player_controls,
    bullet_ammo_capacities_snapshot,
    bullet_ammo_pools_snapshot,
    current_weapon_ammo_snapshot,
    consume_pending_shots,
    follow_player_camera,
    spawn_player_from_level,
)


class GameplayScene(BaseScene):
    name = "gameplay"

    _GAME_OVER_RETURN_TICKS = 80
    _PROJECTILE_MARKER_PIXELS = bytes((252, 252, 252, 252))
    _PROJECTILE_MARKER_SIZE = 2
    _CRATE_FRAME_SIZE = CRATE_SIZE

    def __init__(self) -> None:
        self._renderer: SoftwareRenderer | None = None
        self._level: LevelData | None = None
        self._render_flags = RenderFlags()
        self._camera_x = 0
        self._camera_y = 0
        self._camera_max_x = 0
        self._camera_max_y = 0
        self._spot_phase = 0

        self._player: PlayerState | None = None
        self._held_actions: set[InputAction] = set()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot: int | None = None

        self._static_sprites: tuple[WorldSprite, ...] = ()
        self._target_pixels: bytes | None = None
        self._target_width = 0
        self._target_height = 0
        self._crate_frames: tuple[bytes, ...] = ()
        self._rambo_frames: tuple[bytes, ...] = ()
        self._enemy_frames: dict[int, tuple[bytes, ...]] = {}
        self._enemies: list[EnemyState] = []
        self._crates: list[CrateState] = []
        self._enemy_projectiles: list[EnemyProjectile] = []
        self._enemy_hits_by_player = 0
        self._enemies_killed_by_player = 0
        self._crates_destroyed_by_player = 0
        self._crates_collected_by_player = 0
        self._enemy_shots_fired = 0
        self._enemy_hits_on_player = 0
        self._enemy_damage_to_player = 0.0
        self._game_over_active = False
        self._game_over_ticks_remaining = 0

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.GAMEPLAY
        context.runtime.last_render_digest = 0
        context.runtime.last_render_width = 0
        context.runtime.last_render_height = 0
        context.runtime.player_world_x = 0
        context.runtime.player_world_y = 0
        context.runtime.player_angle_degrees = 0
        context.runtime.player_weapon_slot = 0
        context.runtime.player_current_ammo_type_index = -1
        context.runtime.player_current_ammo_units = 0
        context.runtime.player_current_ammo_capacity = 0
        ammo_capacities = bullet_ammo_capacities_snapshot()
        context.runtime.player_ammo_pools = tuple(0 for _ in ammo_capacities)
        context.runtime.player_ammo_capacities = ammo_capacities
        context.runtime.player_load_count = 0
        context.runtime.player_fire_ticks = 0
        context.runtime.player_shots_fired_total = 0
        context.runtime.player_health = 0
        context.runtime.player_dead = False
        context.runtime.player_hits_total = 0
        context.runtime.player_hits_taken_total = 0
        context.runtime.player_damage_taken_total = 0.0
        context.runtime.enemies_total = 0
        context.runtime.enemies_alive = 0
        context.runtime.enemies_killed_by_player = 0
        context.runtime.crates_total = 0
        context.runtime.crates_alive = 0
        context.runtime.crates_destroyed_by_player = 0
        context.runtime.crates_collected_by_player = 0
        context.runtime.enemy_shots_fired_total = 0
        context.runtime.enemy_hits_total = 0
        context.runtime.enemy_damage_to_player_total = 0.0
        context.runtime.enemy_projectiles_active = 0
        context.runtime.game_over_active = False
        context.runtime.game_over_ticks_remaining = 0

        self._held_actions.clear()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None
        self._target_pixels = None
        self._target_width = 0
        self._target_height = 0
        self._crate_frames = ()
        self._rambo_frames = ()
        self._enemy_frames = {}
        self._enemies = []
        self._crates = []
        self._enemy_projectiles = []
        self._enemy_hits_by_player = 0
        self._enemies_killed_by_player = 0
        self._crates_destroyed_by_player = 0
        self._crates_collected_by_player = 0
        self._enemy_shots_fired = 0
        self._enemy_hits_on_player = 0
        self._enemy_damage_to_player = 0.0
        self._game_over_active = False
        self._game_over_ticks_remaining = 0
        self._static_sprites = ()
        self._spot_phase = 0
        self._render_flags = RenderFlags()

        repo = GameDataRepository(context.paths)
        episode = "DEFAULT"
        level_name = f"LEVEL{max(1, context.session.level_index + 1)}.LEV"

        try:
            level = repo.load_lev(level_name, episode=episode)
        except FileNotFoundError:
            level_name = "LEVEL1.LEV"
            try:
                level = repo.load_lev(level_name, episode=episode)
            except FileNotFoundError as exc:
                context.logger.error("Gameplay level load failed: %s", exc)
                self._renderer = None
                self._level = None
                self._player = None
                return

        try:
            floor_sheet = repo.load_efp("FLOOR1.EFP")
            wall_sheet = repo.load_efp("WALLS1.EFP")
            shadow_sheet = repo.load_efp("SHADOWS.EFP")
            palette_tables = repo.load_palette_tables()
            self._renderer = SoftwareRenderer.from_assets(
                level=level,
                floor_image=floor_sheet,
                wall_image=wall_sheet,
                shadow_image=shadow_sheet,
                palette_tables=palette_tables,
            )
        except (FileNotFoundError, ValueError) as exc:
            self._renderer = None
            self._level = None
            self._player = None
            context.logger.error("Gameplay renderer initialization failed: %s", exc)
            return

        self._level = level
        self._player = spawn_player_from_level(level)

        options = repo.try_load_options()
        if options is not None:
            self._render_flags = RenderFlags(
                dark_mode=bool(options.dark_mode),
                light_effects=bool(options.light_effects),
                shadows=bool(options.shadows),
            )

        player = self._player
        camera_x = int(player.center_x) - (SCREEN_WIDTH // 2)
        camera_y = int(player.center_y) - (SCREEN_HEIGHT // 2)
        self._camera_x, self._camera_y = self._renderer.clamp_camera(camera_x, camera_y)
        self._camera_max_x = self._renderer.max_camera_x
        self._camera_max_y = self._renderer.max_camera_y

        self._static_sprites = ()
        self._target_pixels, self._target_width, self._target_height = self._load_target_sprite(repo)
        self._crate_frames = self._load_crate_frames(repo)
        self._rambo_frames = self._load_rambo_frames(repo)
        self._enemy_frames = self._load_enemy_frames(repo)
        self._enemies = list(
            spawn_enemies_for_level(
                self._level,
                player_x=player.x,
                player_y=player.y,
            ),
        )
        self._crates = list(
            spawn_crates_for_level(
                self._level,
                player_x=player.x,
                player_y=player.y,
            ),
        )

        self._publish_player_runtime_state(context)
        context.logger.info(
            "Gameplay phase-4 controls ready: %s/%s dark=%s lights=%s shadows=%s enemies=%d crates=%d",
            episode,
            level_name,
            self._render_flags.dark_mode,
            self._render_flags.light_effects,
            self._render_flags.shadows,
            len(self._enemies),
            len(self._crates),
        )

    def on_exit(self, context: GameContext) -> None:
        del context
        self._held_actions.clear()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None
        self._game_over_active = False
        self._game_over_ticks_remaining = 0
        self._enemies.clear()
        self._crates.clear()
        self._enemy_projectiles.clear()
        self._crates_destroyed_by_player = 0
        self._crates_collected_by_player = 0

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> None:
        del context
        if self._game_over_active:
            return None

        for event in events:
            if event.type == EventType.ACTION_PRESSED and event.action is not None:
                if event.action == InputAction.NEXT_WEAPON:
                    self._cycle_weapon_requested = True
                else:
                    self._held_actions.add(event.action)
                continue

            if event.type == EventType.ACTION_RELEASED and event.action is not None:
                if event.action != InputAction.NEXT_WEAPON:
                    self._held_actions.discard(event.action)
                continue

            if event.type == EventType.WEAPON_SELECT and event.weapon_slot is not None:
                self._pending_weapon_slot = event.weapon_slot

        return None

    def update(self, context: GameContext, dt_seconds: float) -> SceneTransition | None:
        del dt_seconds
        if self._renderer is None or self._level is None or self._player is None:
            return None

        transition = self._update_game_over_flow(context)
        if transition is not None:
            context.runtime.mode = AppMode.GAME_OVER
        elif not self._game_over_active:
            context.runtime.mode = AppMode.GAMEPLAY

            apply_player_controls(
                self._player,
                self._level,
                self._held_actions,
                cycle_weapon=self._cycle_weapon_requested,
                select_weapon_slot=self._pending_weapon_slot,
            )
            collected = collect_crates_for_player(self._crates, self._player)
            self._crates_collected_by_player += collected.crates_collected
            self._resolve_pending_player_shots()

            report = update_enemy_behavior(
                self._level,
                self._enemies,
                self._player,
                enemy_projectiles=self._enemy_projectiles,
            )
            projectile_report = update_enemy_projectiles(
                self._level,
                self._enemy_projectiles,
                self._player,
                crates=self._crates,
            )
            self._enemy_shots_fired += report.shots_fired
            self._enemy_hits_on_player += report.hits_on_player + projectile_report.hits_on_player
            self._enemy_damage_to_player += report.damage_to_player + projectile_report.damage_to_player
            advance_enemy_effects(self._enemies)
            advance_crate_effects(self._crates)

            if self._player.dead:
                self._activate_game_over(context)
                transition = self._update_game_over_flow(context)
        else:
            context.runtime.mode = AppMode.GAME_OVER

        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None

        self._spot_phase = (self._spot_phase + 2) % 360
        self._camera_x, self._camera_y = follow_player_camera(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            player=self._player,
            max_camera_x=self._camera_max_x,
            max_camera_y=self._camera_max_y,
        )

        self._publish_player_runtime_state(context)
        return transition

    def render(self, context: GameContext, alpha: float) -> None:
        del alpha
        if self._renderer is None:
            return

        sprites = self._compose_world_sprites()
        pixels = self._renderer.render(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            flags=self._render_flags,
            spot_phase_degrees=self._spot_phase,
            sprites=sprites,
        )

        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_digest = frame_digest(pixels)

    def _compose_world_sprites(self) -> tuple[WorldSprite, ...]:
        sprites = list(self._static_sprites)
        if self._player is None:
            return tuple(sprites)

        if self._crate_frames:
            frame_count = len(self._crate_frames)
            for crate in self._crates:
                if not crate.alive:
                    continue

                frame_index = _crate_frame_index(crate, frame_count)
                if crate.hit_flash_ticks > 0 and frame_count > 1:
                    frame_index = (frame_index + 1) % frame_count

                sprites.append(
                    WorldSprite(
                        world_x=int(crate.center_x),
                        world_y=int(crate.center_y),
                        width=self._CRATE_FRAME_SIZE,
                        height=self._CRATE_FRAME_SIZE,
                        pixels=self._crate_frames[frame_index],
                        anchor_x=self._CRATE_FRAME_SIZE // 2,
                        anchor_y=self._CRATE_FRAME_SIZE // 2,
                        translucent=False,
                    ),
                )

        for enemy in self._enemies:
            if not enemy.alive:
                continue
            frames = self._enemy_frames.get(enemy.type_index)
            if not frames:
                continue

            angle_index = (enemy.angle // 9) % len(frames)
            sprites.append(
                WorldSprite(
                    world_x=int(enemy.center_x),
                    world_y=int(enemy.center_y),
                    width=28,
                    height=28,
                    pixels=frames[angle_index],
                    anchor_x=PLAYER_CENTER_OFFSET,
                    anchor_y=PLAYER_CENTER_OFFSET,
                    translucent=False,
                ),
            )

        for projectile in self._enemy_projectiles:
            sprites.append(
                WorldSprite(
                    world_x=int(projectile.x),
                    world_y=int(projectile.y),
                    width=self._PROJECTILE_MARKER_SIZE,
                    height=self._PROJECTILE_MARKER_SIZE,
                    pixels=self._PROJECTILE_MARKER_PIXELS,
                    anchor_x=self._PROJECTILE_MARKER_SIZE // 2,
                    anchor_y=self._PROJECTILE_MARKER_SIZE // 2,
                    translucent=False,
                ),
            )

        if self._rambo_frames:
            angle_index = (self._player.angle // 9) % len(self._rambo_frames)
            sprites.append(
                WorldSprite(
                    world_x=int(self._player.center_x),
                    world_y=int(self._player.center_y),
                    width=28,
                    height=28,
                    pixels=self._rambo_frames[angle_index],
                    anchor_x=PLAYER_CENTER_OFFSET,
                    anchor_y=PLAYER_CENTER_OFFSET,
                    translucent=False,
                ),
            )

        if self._target_pixels is not None:
            target_x, target_y = aim_point_from_player(self._player)
            sprites.append(
                WorldSprite(
                    world_x=target_x,
                    world_y=target_y,
                    width=self._target_width,
                    height=self._target_height,
                    pixels=self._target_pixels,
                    anchor_x=self._target_width // 2,
                    anchor_y=self._target_height // 2,
                    translucent=True,
                ),
            )

            if self._player.shot_effect_ticks > 0:
                sprites.append(
                    WorldSprite(
                        world_x=self._player.shot_effect_x,
                        world_y=self._player.shot_effect_y,
                        width=self._target_width,
                        height=self._target_height,
                        pixels=self._target_pixels,
                        anchor_x=self._target_width // 2,
                        anchor_y=self._target_height // 2,
                        translucent=False,
                    ),
                )

        return tuple(sprites)

    def _load_crate_frames(self, repo: GameDataRepository) -> tuple[bytes, ...]:
        try:
            crate_sheet = repo.load_efp("CRATES.EFP")
        except FileNotFoundError:
            return ()

        frames: list[bytes] = []
        frame_count = max(0, crate_sheet.width // self._CRATE_FRAME_SIZE)
        for frame_index in range(frame_count):
            try:
                frames.append(
                    extract_horizontal_sprite_frame(
                        crate_sheet,
                        frame_width=self._CRATE_FRAME_SIZE,
                        frame_height=self._CRATE_FRAME_SIZE,
                        frame_index=frame_index,
                    ),
                )
            except ValueError:
                break

        return tuple(frames)

    def _load_target_sprite(self, repo: GameDataRepository) -> tuple[bytes | None, int, int]:
        try:
            target = repo.load_efp("TARGET.EFP")
            return target.pixels, target.width, target.height
        except FileNotFoundError:
            return None, 0, 0

    def _load_rambo_frames(self, repo: GameDataRepository) -> tuple[bytes, ...]:
        try:
            rambo_sheet = repo.load_efp("RAMBO2.EFP")
        except FileNotFoundError:
            return ()

        try:
            return _extract_actor_frames(rambo_sheet, animation_row=1)
        except ValueError:
            return ()

    def _load_enemy_frames(self, repo: GameDataRepository) -> dict[int, tuple[bytes, ...]]:
        frames: dict[int, tuple[bytes, ...]] = {}
        for enemy_type in range(8):
            try:
                image = repo.load_efp(f"ENEMY{enemy_type}.EFP")
            except FileNotFoundError:
                continue

            try:
                frames[enemy_type] = _extract_actor_frames(image, animation_row=1)
            except ValueError:
                continue
        return frames

    def _resolve_pending_player_shots(self) -> None:
        if self._level is None or self._player is None:
            return

        for shot in consume_pending_shots(self._player):
            result = resolve_shot_against_enemies(
                self._level,
                self._enemies,
                shot,
                crates=self._crates,
            )
            self._player.shot_effect_x = result.impact_x
            self._player.shot_effect_y = result.impact_y
            if result.enemy_id is not None:
                self._enemy_hits_by_player += 1
            if result.enemy_killed:
                self._enemies_killed_by_player += 1
            if result.crate_destroyed:
                self._crates_destroyed_by_player += 1

    def _activate_game_over(self, context: GameContext) -> None:
        if self._game_over_active:
            return

        self._game_over_active = True
        self._game_over_ticks_remaining = self._GAME_OVER_RETURN_TICKS
        self._held_actions.clear()
        self._cycle_weapon_requested = False
        self._pending_weapon_slot = None
        self._enemy_projectiles.clear()
        context.runtime.mode = AppMode.GAME_OVER
        context.logger.info(
            "Player died, entering game-over flow (%d ticks)",
            self._GAME_OVER_RETURN_TICKS,
        )

    def _update_game_over_flow(self, context: GameContext) -> SceneTransition | None:
        if not self._game_over_active:
            return None

        if self._game_over_ticks_remaining > 0:
            self._game_over_ticks_remaining -= 1
        if self._game_over_ticks_remaining > 0:
            return None

        self._game_over_active = False
        self._game_over_ticks_remaining = 0
        context.logger.info("Game-over flow complete, returning to main menu")
        from ultimatetk.ui.main_menu_scene import MainMenuScene

        return SceneTransition(next_scene=MainMenuScene(autostart_enabled=False))

    def _publish_player_runtime_state(self, context: GameContext) -> None:
        if self._player is None:
            context.runtime.player_world_x = 0
            context.runtime.player_world_y = 0
            context.runtime.player_angle_degrees = 0
            context.runtime.player_weapon_slot = 0
            context.runtime.player_current_ammo_type_index = -1
            context.runtime.player_current_ammo_units = 0
            context.runtime.player_current_ammo_capacity = 0
            ammo_capacities = bullet_ammo_capacities_snapshot()
            context.runtime.player_ammo_pools = tuple(0 for _ in ammo_capacities)
            context.runtime.player_ammo_capacities = ammo_capacities
            context.runtime.player_load_count = 0
            context.runtime.player_fire_ticks = 0
            context.runtime.player_shots_fired_total = 0
            context.runtime.player_health = 0
            context.runtime.player_dead = False
            context.runtime.player_hits_total = 0
            context.runtime.player_hits_taken_total = 0
            context.runtime.player_damage_taken_total = 0.0
            context.runtime.enemies_total = 0
            context.runtime.enemies_alive = 0
            context.runtime.enemies_killed_by_player = 0
            context.runtime.crates_total = 0
            context.runtime.crates_alive = 0
            context.runtime.crates_destroyed_by_player = 0
            context.runtime.crates_collected_by_player = 0
            context.runtime.enemy_shots_fired_total = 0
            context.runtime.enemy_hits_total = 0
            context.runtime.enemy_damage_to_player_total = 0.0
            context.runtime.enemy_projectiles_active = 0
            context.runtime.game_over_active = False
            context.runtime.game_over_ticks_remaining = 0
            return

        context.runtime.player_world_x = int(self._player.center_x)
        context.runtime.player_world_y = int(self._player.center_y)
        context.runtime.player_angle_degrees = self._player.angle
        context.runtime.player_weapon_slot = self._player.current_weapon
        (
            context.runtime.player_current_ammo_type_index,
            context.runtime.player_current_ammo_units,
            context.runtime.player_current_ammo_capacity,
        ) = current_weapon_ammo_snapshot(self._player)
        context.runtime.player_ammo_pools = bullet_ammo_pools_snapshot(self._player)
        context.runtime.player_ammo_capacities = bullet_ammo_capacities_snapshot()
        context.runtime.player_load_count = self._player.load_count
        context.runtime.player_fire_ticks = self._player.fire_animation_ticks
        context.runtime.player_shots_fired_total = self._player.shots_fired_total
        context.runtime.player_health = int(self._player.health)
        context.runtime.player_dead = self._player.dead
        context.runtime.player_hits_total = self._enemy_hits_by_player
        context.runtime.player_hits_taken_total = self._player.hits_taken_total
        context.runtime.player_damage_taken_total = self._player.damage_taken_total
        context.runtime.enemies_total = len(self._enemies)
        context.runtime.enemies_alive = alive_enemy_count(self._enemies)
        context.runtime.enemies_killed_by_player = self._enemies_killed_by_player
        context.runtime.crates_total = len(self._crates)
        context.runtime.crates_alive = alive_crate_count(self._crates)
        context.runtime.crates_destroyed_by_player = self._crates_destroyed_by_player
        context.runtime.crates_collected_by_player = self._crates_collected_by_player
        context.runtime.enemy_shots_fired_total = self._enemy_shots_fired
        context.runtime.enemy_hits_total = self._enemy_hits_on_player
        context.runtime.enemy_damage_to_player_total = self._enemy_damage_to_player
        context.runtime.enemy_projectiles_active = len(self._enemy_projectiles)
        context.runtime.game_over_active = self._game_over_active
        context.runtime.game_over_ticks_remaining = self._game_over_ticks_remaining


def _crate_frame_index(crate: CrateState, frame_count: int) -> int:
    if frame_count <= 0:
        return 0

    seed = (max(0, crate.type1) * 17) + (max(0, crate.type2) * 7)
    return seed % frame_count


def _extract_actor_frames(image: EfpImage, *, animation_row: int) -> tuple[bytes, ...]:
    frame_width = 28
    frame_height = 28
    frame_stride = 29

    row_y = 1 + (animation_row * frame_stride)
    if row_y < 0 or row_y + frame_height > image.height:
        raise ValueError("invalid actor animation row")

    angle_frames = image.width // frame_stride
    if angle_frames <= 0:
        raise ValueError("actor sprite sheet has no angle frames")

    frames: list[bytes] = []
    for angle in range(angle_frames):
        src_x = 1 + (angle * frame_stride)
        if src_x + frame_width > image.width:
            break

        frame = bytearray(frame_width * frame_height)
        for row in range(frame_height):
            src_start = (row_y + row) * image.width + src_x
            dst_start = row * frame_width
            frame[dst_start : dst_start + frame_width] = image.pixels[src_start : src_start + frame_width]
        frames.append(bytes(frame))

    if not frames:
        raise ValueError("failed to extract actor angle frames")
    return tuple(frames)
