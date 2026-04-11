from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ultimatetk.assets import GameDataRepository
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, EventType, InputAction
from ultimatetk.core.scenes import BaseScene, SceneTransition
from ultimatetk.core.state import AppMode
from ultimatetk.formats.efp import EfpImage
from ultimatetk.formats.fnt import FontFile
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
    PlayerExplosive,
    advance_crate_effects,
    advance_enemy_effects,
    alive_crate_count,
    alive_enemy_count,
    collect_crates_for_player,
    deploy_player_explosive_from_shot,
    is_player_explosive_weapon_slot,
    resolve_shot_against_enemies,
    spawn_crates_for_level,
    spawn_enemies_for_level,
    update_player_explosives,
    update_enemy_behavior,
    update_enemy_projectiles,
)
from ultimatetk.systems.player_control import (
    PLAYER_CENTER_OFFSET,
    PlayerState,
    SHOP_ROW_AMMO,
    SHOP_ROW_OTHER,
    SHOP_SHIELD_MAX_LEVEL,
    SHOP_ROW_WEAPONS,
    SHOP_SHIELD_LEVEL_COST_STEP,
    SHOP_TARGET_SYSTEM_COST,
    ShopSellPriceTable,
    ShopTransactionEvent,
    aim_point_from_player,
    apply_player_controls,
    bullet_ammo_capacities_snapshot,
    bullet_capacity_units_for_type,
    bullet_shop_name_for_type,
    bullet_shop_short_label_for_type,
    bullet_ammo_pools_snapshot,
    bullet_shop_cost_for_type,
    bullet_shop_units_for_type,
    buy_selected_shop_item,
    clamp_shop_selection,
    consume_pending_shots,
    current_weapon_ammo_snapshot,
    follow_player_camera,
    generate_shop_sell_prices,
    move_shop_selection,
    player_health_capacity,
    sell_selected_shop_item,
    shield_shop_buy_cost_for_level,
    shop_column_count_for_row,
    weapon_shop_name_for_slot,
    weapon_shop_short_label_for_slot,
    spawn_player_from_level,
    weapon_bullet_type_index_for_slot,
    weapon_profile_for_slot,
    weapon_sell_price_for_slot,
    weapon_shop_cost_for_slot,
)


@dataclass(frozen=True, slots=True)
class GameplayStateView:
    level: LevelData
    player: PlayerState
    enemies: tuple[EnemyState, ...]
    crates: tuple[CrateState, ...]
    enemy_projectiles: tuple[EnemyProjectile, ...]
    player_explosives: tuple[PlayerExplosive, ...]
    shop_active: bool


class GameplayScene(BaseScene):
    name = "gameplay"

    _GAME_OVER_RETURN_TICKS = 80
    _DEFAULT_EPISODE = "DEFAULT"
    _PROJECTILE_MARKER_PIXELS = bytes((252, 252, 252, 252))
    _PROJECTILE_MARKER_SIZE = 2
    _PLAYER_EXPLOSIVE_MARKER_SIZE = 3
    _PLAYER_C4_MARKER_PIXELS = bytes((28,)) * (_PLAYER_EXPLOSIVE_MARKER_SIZE * _PLAYER_EXPLOSIVE_MARKER_SIZE)
    _PLAYER_MINE_MARKER_PIXELS = bytes((112,)) * (_PLAYER_EXPLOSIVE_MARKER_SIZE * _PLAYER_EXPLOSIVE_MARKER_SIZE)
    _CRATE_FRAME_SIZE = CRATE_SIZE
    _SHOP_GRID_ORIGIN_X = 8
    _SHOP_GRID_ORIGIN_Y = 132
    _SHOP_CELL_SIZE = 16
    _SHOP_CELL_GAP = 2
    _SHOP_TEXT_COLOR = 113
    _SHOP_VALUE_COLOR = 126
    _SHOP_MUTED_COLOR = 76
    _SHOP_PANEL_COLOR = 13
    _SHOP_CELL_COLOR = 8
    _SHOP_BORDER_COLOR = 98
    _SHOP_SELECTED_COLOR = 96
    _SHOP_ICON_COLOR = 117
    _SHOP_ICON_SELECTED_COLOR = 126
    _SHOP_LOCKED_CELL_COLOR = 6
    _SHOP_UNAFFORDABLE_CELL_COLOR = 4
    _SHOP_STATE_MARKER_SIZE = 2
    _SHOP_SUCCESS_COLOR = 112
    _SHOP_ERROR_COLOR = 28
    _SHOP_CELL_TEXT_MAX_CHARS = 2
    _HUD_PANEL_COLOR = 13
    _HUD_CELL_COLOR = 8
    _HUD_BORDER_COLOR = 98
    _HUD_TEXT_COLOR = 113
    _HUD_VALUE_COLOR = 126
    _HUD_MUTED_COLOR = 76
    _HUD_WARN_COLOR = 28
    _HUD_OK_COLOR = 112
    _C4_HOT_FUSE_TICKS = 12
    _SHOP_ICON_BITMAPS: dict[str, tuple[str, ...]] = {
        "w_pistol": (
            "..###..",
            "..#....",
            ".#####.",
            "...#...",
            "..##...",
            ".......",
            ".......",
        ),
        "w_shotgun": (
            ".######",
            ".#.....",
            "######.",
            "....##.",
            ".....#.",
            ".......",
            ".......",
        ),
        "w_uzi": (
            ".####..",
            ".#..##.",
            ".#####.",
            "...##..",
            "..##...",
            ".......",
            ".......",
        ),
        "w_rifle": (
            "#######",
            "#....##",
            "######.",
            "..#....",
            ".##....",
            ".......",
            ".......",
        ),
        "w_gl": (
            ".#####.",
            ".#...##",
            "######.",
            "....##.",
            "...##..",
            ".......",
            ".......",
        ),
        "w_ag": (
            ".#####.",
            ".#.#.#.",
            "#######",
            "..#.#..",
            ".##.##.",
            ".......",
            ".......",
        ),
        "w_hl": (
            "#######",
            "##...##",
            "#######",
            "..###..",
            "..###..",
            "...#...",
            ".......",
        ),
        "w_as": (
            "#######",
            "#.#.#.#",
            "#######",
            "..###..",
            ".##.##.",
            "...#...",
            ".......",
        ),
        "w_c4": (
            ".#####.",
            ".#.#.#.",
            ".#####.",
            "...#...",
            "..###..",
            "...#...",
            ".......",
        ),
        "w_flame": (
            "...#...",
            "..###..",
            ".#####.",
            ".##.##.",
            "..###..",
            "...#...",
            ".......",
        ),
        "w_mine": (
            "..###..",
            ".#####.",
            "##.#.##",
            ".#####.",
            "..###..",
            "..#.#..",
            ".......",
        ),
        "w_generic": (
            ".#####.",
            ".#...#.",
            ".#####.",
            "...#...",
            "..###..",
            ".......",
            ".......",
        ),
        "a_9mm": (
            ".#.#...",
            ".#.#...",
            ".#.#...",
            ".#.#...",
            "..#....",
            ".......",
            ".......",
        ),
        "a_12mm": (
            ".##.##.",
            ".##.##.",
            ".##.##.",
            ".##.##.",
            "..#.#..",
            "...#...",
            ".......",
        ),
        "a_shell": (
            ".#####.",
            ".#...#.",
            ".#...#.",
            ".#####.",
            "..###..",
            "...#...",
            ".......",
        ),
        "a_lg": (
            "...#...",
            "..###..",
            ".#####.",
            ".#####.",
            "..###..",
            "...#...",
            ".......",
        ),
        "a_mg": (
            "..###..",
            ".#####.",
            "#######",
            "#######",
            ".#####.",
            "..###..",
            "...#...",
        ),
        "a_hg": (
            ".#####.",
            "#######",
            "#######",
            "#######",
            ".#####.",
            "..###..",
            "...#...",
        ),
        "a_c4": (
            ".#####.",
            ".#...#.",
            ".##.##.",
            ".#...#.",
            ".#####.",
            "..#.#..",
            ".......",
        ),
        "a_gas": (
            "..###..",
            ".#...#.",
            ".#.#.#.",
            ".#####.",
            ".#...#.",
            ".#####.",
            ".......",
        ),
        "a_mine": (
            "..###..",
            ".#####.",
            "##.#.##",
            ".#####.",
            "..###..",
            "..#.#..",
            ".......",
        ),
        "shield": (
            "..###..",
            ".#####.",
            ".#...#.",
            ".#####.",
            "..###..",
            "...#...",
            ".......",
        ),
        "target": (
            ".#####.",
            ".#...#.",
            ".#.#.#.",
            ".#...#.",
            ".#####.",
            "...#...",
            ".......",
        ),
    }

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
        self._shop_active = False
        self._shop_row = 0
        self._shop_column = 0
        self._shop_sell_prices = ShopSellPriceTable(
            weapon_slots=(),
            shield_base=0,
            target_system=0,
        )
        self._shop_last_transaction: ShopTransactionEvent | None = None
        self._static_sprites: tuple[WorldSprite, ...] = ()
        self._progression_enabled = False
        self._reset_input_flags()
        self._reset_entity_holders()
        self._reset_stat_counters()

    # ------------------------------------------------------------------
    # State reset helpers
    # ------------------------------------------------------------------

    def _reset_input_flags(self) -> None:
        """Clear all per-tick input/shop-navigation request flags."""
        self._cycle_weapon_requested = False
        self._pending_weapon_slot: int | None = None
        self._shop_nav_row_delta = 0
        self._shop_nav_column_delta = 0
        self._shop_buy_requested = False
        self._shop_sell_requested = False
        self._shop_toggle_requested = False

    def _reset_entity_holders(self) -> None:
        """Reset asset caches and entity lists to empty defaults."""
        self._ui_font: FontFile | None = None
        self._target_pixels: bytes | None = None
        self._target_width = 0
        self._target_height = 0
        self._crate_frames: tuple[bytes, ...] = ()
        self._rambo_frames: tuple[bytes, ...] = ()
        self._enemy_frames: dict[int, tuple[bytes, ...]] = {}
        self._enemies: list[EnemyState] = []
        self._crates: list[CrateState] = []
        self._enemy_projectiles: list[EnemyProjectile] = []
        self._player_explosives: list[PlayerExplosive] = []

    def _reset_stat_counters(self) -> None:
        """Zero all gameplay stat accumulators."""
        self._player_explosive_detonations = 0
        self._enemy_hits_by_player = 0
        self._enemies_killed_by_player = 0
        self._crates_destroyed_by_player = 0
        self._crates_collected_by_player = 0
        self._enemy_shots_fired = 0
        self._enemy_hits_on_player = 0
        self._enemy_damage_to_player = 0.0
        self._game_over_active = False
        self._game_over_ticks_remaining = 0

    def _publish_zeroed_runtime_state(self, context: GameContext) -> None:
        """Set all player/combat/shop runtime fields to neutral defaults."""
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
        context.runtime.player_cash = 0
        context.runtime.player_shield = 0
        context.runtime.player_target_system_enabled = False
        context.runtime.shop_active = False
        context.runtime.shop_selection_row = 0
        context.runtime.shop_selection_column = 0
        self._publish_zeroed_shop_last_fields(context)
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
        context.runtime.player_explosives_active = 0
        context.runtime.player_mines_active = 0
        context.runtime.player_mines_armed = 0
        context.runtime.player_c4_active = 0
        context.runtime.player_c4_hot = 0
        context.runtime.player_explosive_detonations_total = 0
        context.runtime.game_over_active = False
        context.runtime.game_over_ticks_remaining = 0

    @staticmethod
    def _publish_zeroed_shop_last_fields(context: GameContext) -> None:
        """Reset all ``shop_last_*`` runtime fields to neutral defaults."""
        context.runtime.shop_last_action = ""
        context.runtime.shop_last_category = ""
        context.runtime.shop_last_success = False
        context.runtime.shop_last_units = 0
        context.runtime.shop_last_cash_delta = 0
        context.runtime.shop_last_reason = ""

    def on_enter(self, context: GameContext) -> None:
        context.runtime.mode = AppMode.GAMEPLAY
        context.runtime.last_render_digest = 0
        context.runtime.last_render_width = 0
        context.runtime.last_render_height = 0
        self._publish_zeroed_runtime_state(context)
        context.runtime.progression_event = ""
        context.runtime.progression_from_level_index = -1
        context.runtime.progression_to_level_index = -1
        context.runtime.progression_has_next_level = False
        context.runtime.progression_ticks_remaining = 0

        self._held_actions.clear()
        self._reset_input_flags()
        self._shop_active = False
        self._shop_row = 0
        self._shop_column = 0
        self._shop_sell_prices = ShopSellPriceTable(
            weapon_slots=(),
            shield_base=0,
            target_system=0,
        )
        self._shop_last_transaction = None
        self._reset_entity_holders()
        self._reset_stat_counters()
        self._progression_enabled = not context.config.autostart_gameplay
        self._static_sprites = ()
        self._spot_phase = 0
        self._render_flags = RenderFlags()

        repo = GameDataRepository(context.paths)
        episode = self._DEFAULT_EPISODE
        level_name = self._level_name_for_session_index(context.session.level_index)
        self._ui_font = self._load_ui_font(repo)

        try:
            level = repo.load_lev(level_name, episode=episode)
        except FileNotFoundError:
            level_name = "LEVEL1.LEV"
            context.session.level_index = 0
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
        self._shop_sell_prices = generate_shop_sell_prices(
            random_seed=self._sell_seed(context),
        )
        self._shop_row, self._shop_column = clamp_shop_selection(0, 0)

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
            "Gameplay phase-4 controls ready: %s/%s dark=%s lights=%s shadows=%s enemies=%d crates=%d shop_seed=%d",
            episode,
            level_name,
            self._render_flags.dark_mode,
            self._render_flags.light_effects,
            self._render_flags.shadows,
            len(self._enemies),
            len(self._crates),
            self._sell_seed(context),
        )

    def on_exit(self, context: GameContext) -> None:
        del context
        self._held_actions.clear()
        self._reset_input_flags()
        self._shop_active = False
        self._shop_last_transaction = None
        self._ui_font = None
        self._game_over_active = False
        self._game_over_ticks_remaining = 0
        self._enemies.clear()
        self._crates.clear()
        self._enemy_projectiles.clear()
        self._player_explosives.clear()
        self._crates_destroyed_by_player = 0
        self._crates_collected_by_player = 0

    def handle_events(self, context: GameContext, events: Sequence[AppEvent]) -> None:
        del context
        if self._game_over_active:
            return None

        for event in events:
            if event.type == EventType.ACTION_PRESSED and event.action is not None:
                if event.action == InputAction.TOGGLE_SHOP:
                    self._shop_toggle_requested = True
                    continue

                if self._shop_active:
                    self._queue_shop_action(event.action)
                    continue

                if event.action == InputAction.NEXT_WEAPON:
                    self._cycle_weapon_requested = True
                else:
                    self._held_actions.add(event.action)
                continue

            if event.type == EventType.ACTION_RELEASED and event.action is not None:
                if self._shop_active:
                    continue
                if event.action not in (InputAction.NEXT_WEAPON, InputAction.TOGGLE_SHOP):
                    self._held_actions.discard(event.action)
                continue

            if event.type == EventType.WEAPON_SELECT and event.weapon_slot is not None:
                if self._shop_active:
                    continue
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

            if self._player.dead:
                self._activate_game_over(context)
                transition = self._update_game_over_flow(context)
            else:
                if self._shop_toggle_requested:
                    self._toggle_shop(context)

                if self._shop_active:
                    self._update_shop_state(context)
                else:
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

                    explosive_report = update_player_explosives(
                        self._player_explosives,
                        self._enemies,
                        self._player,
                        level=self._level,
                        crates=self._crates,
                    )
                    self._player_explosive_detonations += explosive_report.detonations
                    self._enemy_hits_by_player += explosive_report.enemies_hit
                    self._enemies_killed_by_player += explosive_report.enemies_killed
                    self._crates_destroyed_by_player += explosive_report.crates_destroyed

                    report = update_enemy_behavior(
                        self._level,
                        self._enemies,
                        self._player,
                        enemy_projectiles=self._enemy_projectiles,
                        crates=self._crates,
                    )
                    projectile_report = update_enemy_projectiles(
                        self._level,
                        self._enemy_projectiles,
                        self._player,
                        crates=self._crates,
                        enemies=self._enemies,
                    )
                    self._enemy_shots_fired += report.shots_fired
                    self._enemy_hits_on_player += report.hits_on_player + projectile_report.hits_on_player
                    self._enemy_damage_to_player += report.damage_to_player + projectile_report.damage_to_player
                    advance_enemy_effects(self._enemies)
                    advance_crate_effects(self._crates)

                    if self._player.dead:
                        self._activate_game_over(context)
                        transition = self._update_game_over_flow(context)
                    elif transition is None and self._should_advance_level_progression():
                        transition = self._advance_level_progression(context)
        else:
            context.runtime.mode = AppMode.GAME_OVER

        self._reset_input_flags()

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
            context.runtime.last_render_width = 0
            context.runtime.last_render_height = 0
            context.runtime.last_render_pixels = b""
            context.runtime.last_render_palette = b""
            context.runtime.last_render_digest = 0
            return

        sprites = self._compose_world_sprites()
        pixels = self._renderer.render(
            camera_x=self._camera_x,
            camera_y=self._camera_y,
            flags=self._render_flags,
            spot_phase_degrees=self._spot_phase,
            sprites=sprites,
        )

        if self._player is not None and self._shop_active:
            overlay_pixels = bytearray(pixels)
            self._draw_shop_overlay(overlay_pixels)
            pixels = bytes(overlay_pixels)
        elif self._player is not None:
            overlay_pixels = bytearray(pixels)
            self._draw_gameplay_hud(overlay_pixels)
            pixels = bytes(overlay_pixels)

        context.runtime.last_render_width = SCREEN_WIDTH
        context.runtime.last_render_height = SCREEN_HEIGHT
        context.runtime.last_render_pixels = pixels
        context.runtime.last_render_palette = self._renderer.palette_bytes
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

        for explosive in self._player_explosives:
            marker_pixels = self._PLAYER_MINE_MARKER_PIXELS
            if explosive.kind == "c4":
                marker_pixels = self._PLAYER_C4_MARKER_PIXELS

            sprites.append(
                WorldSprite(
                    world_x=int(explosive.x),
                    world_y=int(explosive.y),
                    width=self._PLAYER_EXPLOSIVE_MARKER_SIZE,
                    height=self._PLAYER_EXPLOSIVE_MARKER_SIZE,
                    pixels=marker_pixels,
                    anchor_x=self._PLAYER_EXPLOSIVE_MARKER_SIZE // 2,
                    anchor_y=self._PLAYER_EXPLOSIVE_MARKER_SIZE // 2,
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

        if self._target_pixels is not None and not self._shop_active:
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

    def _load_ui_font(self, repo: GameDataRepository) -> FontFile | None:
        for font_name in ("8X8.FNT", "8X8B.FNT"):
            try:
                return repo.load_fnt(font_name)
            except (FileNotFoundError, ValueError):
                continue
        return None

    def _draw_shop_overlay(self, pixels: bytearray) -> None:
        if self._player is None:
            return

        header_x = 4
        header_y = 4
        header_width = SCREEN_WIDTH - 8
        header_height = 108
        grid_x = self._SHOP_GRID_ORIGIN_X
        grid_y = self._SHOP_GRID_ORIGIN_Y
        cell_pitch = self._SHOP_CELL_SIZE + self._SHOP_CELL_GAP
        grid_height = (cell_pitch * 3) + 4

        self._fill_rect(
            pixels,
            header_x,
            header_y,
            header_width,
            header_height,
            self._SHOP_PANEL_COLOR,
        )
        self._fill_rect(
            pixels,
            header_x + 1,
            header_y + 1,
            header_width - 2,
            10,
            self._SHOP_CELL_COLOR,
        )
        self._stroke_rect(
            pixels,
            header_x,
            header_y,
            header_width,
            header_height,
            self._SHOP_BORDER_COLOR,
        )

        self._fill_rect(
            pixels,
            grid_x - 2,
            grid_y - 2,
            316,
            grid_height,
            self._SHOP_PANEL_COLOR,
        )
        self._stroke_rect(
            pixels,
            grid_x - 2,
            grid_y - 2,
            316,
            grid_height,
            self._SHOP_BORDER_COLOR,
        )

        selection_label, buy_cost, sell_price, selection_state = self._shop_selection_info()
        row_label = self._shop_row_label(self._shop_row)

        self._draw_shop_text(pixels, 10, 7, "THE SHOP", self._SHOP_VALUE_COLOR)
        self._draw_shop_text(pixels, 10, 20, f"CASH {self._player.cash}", self._SHOP_VALUE_COLOR)
        self._draw_shop_text(
            pixels,
            10,
            30,
            f"ROW {row_label} COL {self._shop_column + 1:02d}",
            self._SHOP_TEXT_COLOR,
        )
        self._draw_shop_text(
            pixels,
            10,
            44,
            f"ITEM {selection_label}",
            self._SHOP_VALUE_COLOR,
        )
        self._draw_shop_text(
            pixels,
            10,
            54,
            f"BUY {buy_cost} SELL {sell_price}",
            self._SHOP_TEXT_COLOR,
        )
        self._draw_shop_text(
            pixels,
            10,
            64,
            selection_state,
            self._shop_selection_state_color(),
        )

        feedback_color = self._SHOP_TEXT_COLOR
        feedback_text = "BUY SPACE / SELL TAB"
        if self._shop_last_transaction is not None:
            tx = self._shop_last_transaction
            if tx.success:
                feedback_text = (
                    f"{tx.action.upper()} {tx.category.upper()} OK "
                    f"U{tx.units} C{tx.cash_delta:+d}"
                )
                feedback_color = self._SHOP_SUCCESS_COLOR
            else:
                reason = tx.reason.upper() if tx.reason else "BLOCKED"
                feedback_text = f"{tx.action.upper()} {tx.category.upper()} BLOCKED {reason}"
                feedback_color = self._SHOP_ERROR_COLOR

        self._draw_shop_text(pixels, 10, 78, feedback_text, feedback_color)
        self._draw_shop_text(
            pixels,
            10,
            90,
            "W/S ROW A/D COL SPACE BUY TAB SELL R/ENT",
            self._SHOP_TEXT_COLOR,
        )

        row_labels = ("WEAP", "AMMO", "OTHR")
        for row in range(3):
            columns = shop_column_count_for_row(row)
            row_y = grid_y + (row * cell_pitch)
            row_color = self._SHOP_VALUE_COLOR if row == self._shop_row else self._SHOP_TEXT_COLOR

            self._draw_shop_text(
                pixels,
                214,
                row_y + 4,
                row_labels[row],
                row_color,
            )

            for column in range(columns):
                cell_x = grid_x + (column * cell_pitch)
                selected = row == self._shop_row and column == self._shop_column
                selected_pulse = ((self._spot_phase // 15) % 2) == 0
                cell_state = self._shop_cell_state(row, column)
                (
                    fill_color,
                    border_color,
                    icon_color,
                    label_color,
                    counter_color,
                    marker_color,
                ) = self._shop_cell_visual_colors(
                    row,
                    column,
                    selected=selected,
                    selected_pulse=selected_pulse,
                    state=cell_state,
                )

                self._fill_rect(
                    pixels,
                    cell_x,
                    row_y,
                    self._SHOP_CELL_SIZE,
                    self._SHOP_CELL_SIZE,
                    fill_color,
                )
                self._stroke_rect(
                    pixels,
                    cell_x,
                    row_y,
                    self._SHOP_CELL_SIZE,
                    self._SHOP_CELL_SIZE,
                    border_color,
                )
                if selected and self._SHOP_CELL_SIZE > 4:
                    self._stroke_rect(
                        pixels,
                        cell_x + 1,
                        row_y + 1,
                        self._SHOP_CELL_SIZE - 2,
                        self._SHOP_CELL_SIZE - 2,
                        self._SHOP_BORDER_COLOR,
                    )

                marker_size = max(1, min(self._SHOP_STATE_MARKER_SIZE, self._SHOP_CELL_SIZE - 2))
                self._fill_rect(
                    pixels,
                    cell_x + self._SHOP_CELL_SIZE - marker_size - 1,
                    row_y + 1,
                    marker_size,
                    marker_size,
                    marker_color,
                )

                icon_kind = self._shop_cell_icon_kind(row, column)
                if icon_kind:
                    self._draw_shop_cell_icon(
                        pixels,
                        x=cell_x + 2,
                        y=row_y + 2,
                        kind=icon_kind,
                        color=icon_color,
                    )

                cell_label = self._shop_cell_aligned_text(self._shop_cell_label_text(row, column))
                if cell_label:
                    label_x = self._shop_cell_text_x(cell_x, cell_label)
                    self._draw_shop_text(
                        pixels,
                        label_x,
                        row_y + 1,
                        cell_label,
                        label_color,
                    )

                counter_text = self._shop_cell_counter_text(row, column)
                if counter_text:
                    counter_label = self._shop_cell_aligned_text(counter_text, pad_numeric=True)
                    counter_x = self._shop_cell_text_x(cell_x, counter_label)
                    self._draw_shop_text(
                        pixels,
                        counter_x,
                        row_y + 8,
                        counter_label,
                        counter_color,
                    )

    def _shop_selection_info(self) -> tuple[str, int, int, str]:
        if self._player is None:
            return "-", 0, 0, ""

        if self._shop_row == SHOP_ROW_WEAPONS:
            weapon_slot = self._shop_column + 1
            owned = weapon_slot < len(self._player.weapons) and self._player.weapons[weapon_slot]
            state_text = "OWNED" if owned else "FOR SALE"

            ammo_type = weapon_bullet_type_index_for_slot(weapon_slot)
            if ammo_type is None:
                ammo_text = "MELEE"
            else:
                ammo_text = bullet_shop_name_for_type(ammo_type)

            return (
                weapon_shop_name_for_slot(weapon_slot),
                weapon_shop_cost_for_slot(weapon_slot),
                weapon_sell_price_for_slot(self._shop_sell_prices, weapon_slot),
                f"{state_text} / AMMO {ammo_text}",
            )

        if self._shop_row == SHOP_ROW_AMMO:
            ammo_type = self._shop_column
            stock = self._player.bullets[ammo_type] if ammo_type < len(self._player.bullets) else 0
            units_per_trade = max(1, bullet_shop_units_for_type(ammo_type))
            capacity = bullet_capacity_units_for_type(ammo_type)
            return (
                bullet_shop_name_for_type(ammo_type),
                bullet_shop_cost_for_type(ammo_type),
                bullet_shop_cost_for_type(ammo_type),
                f"STOCK {stock}/{capacity} PACK {units_per_trade}",
            )

        if self._shop_column == 0:
            prior_level = max(0, self._player.shield - 1)
            shield_sell_price = max(0, self._shop_sell_prices.shield_base)
            shield_sell_price += (SHOP_SHIELD_LEVEL_COST_STEP * prior_level) // 2
            return (
                "SHIELD",
                shield_shop_buy_cost_for_level(self._player.shield),
                shield_sell_price,
                f"LEVEL {self._player.shield}/{SHOP_SHIELD_MAX_LEVEL}",
            )

        target_state = "ON" if self._player.target_system_enabled else "OFF"
        return (
            "TARGET",
            SHOP_TARGET_SYSTEM_COST,
            max(0, self._shop_sell_prices.target_system),
            f"STATE {target_state}",
        )

    def _shop_row_label(self, row: int) -> str:
        if row == SHOP_ROW_WEAPONS:
            return "WEAPONS"
        if row == SHOP_ROW_AMMO:
            return "AMMO"
        if row == SHOP_ROW_OTHER:
            return "OTHER"
        return "UNKNOWN"

    def _shop_cell_label_text(self, row: int, column: int) -> str:
        if row == SHOP_ROW_WEAPONS:
            return weapon_shop_short_label_for_slot(column + 1)

        if row == SHOP_ROW_AMMO:
            return bullet_shop_short_label_for_type(column)

        if row == SHOP_ROW_OTHER and column == 0:
            return "SH"

        if row == SHOP_ROW_OTHER and column == 1:
            return "TG"
        return ""

    def _shop_cell_icon_kind(self, row: int, column: int) -> str:
        if row == SHOP_ROW_WEAPONS:
            return self._weapon_shop_icon_kind(column + 1)

        if row == SHOP_ROW_AMMO:
            return self._ammo_shop_icon_kind(column)

        if row == SHOP_ROW_OTHER and column == 0:
            return "shield"
        if row == SHOP_ROW_OTHER and column == 1:
            return "target"
        return ""

    def _weapon_shop_icon_kind(self, weapon_slot: int) -> str:
        if weapon_slot == 1:
            return "w_pistol"
        if weapon_slot == 2:
            return "w_shotgun"
        if weapon_slot == 3:
            return "w_uzi"
        if weapon_slot == 4:
            return "w_rifle"
        if weapon_slot == 5:
            return "w_gl"
        if weapon_slot == 6:
            return "w_ag"
        if weapon_slot == 7:
            return "w_hl"
        if weapon_slot == 8:
            return "w_as"
        if weapon_slot == 9:
            return "w_c4"
        if weapon_slot == 10:
            return "w_flame"
        if weapon_slot == 11:
            return "w_mine"
        return "w_generic"

    def _ammo_shop_icon_kind(self, ammo_type: int) -> str:
        if ammo_type == 0:
            return "a_9mm"
        if ammo_type == 1:
            return "a_12mm"
        if ammo_type == 2:
            return "a_shell"
        if ammo_type == 3:
            return "a_lg"
        if ammo_type == 4:
            return "a_mg"
        if ammo_type == 5:
            return "a_hg"
        if ammo_type == 6:
            return "a_c4"
        if ammo_type == 7:
            return "a_gas"
        if ammo_type == 8:
            return "a_mine"
        return "a_9mm"

    def _draw_shop_cell_icon(self, pixels: bytearray, *, x: int, y: int, kind: str, color: int) -> None:
        if not kind:
            return
        if color < 0 or color > 255:
            return

        pattern = self._SHOP_ICON_BITMAPS.get(kind)
        if pattern is None:
            return
        self._draw_shop_icon_bitmap(pixels, x=x, y=y, pattern=pattern, color=color)

    def _draw_shop_icon_bitmap(
        self,
        pixels: bytearray,
        *,
        x: int,
        y: int,
        pattern: tuple[str, ...],
        color: int,
    ) -> None:
        if color < 0 or color > 255:
            return

        for row_index, row in enumerate(pattern):
            for column_index, marker in enumerate(row):
                if marker != "#":
                    continue
                self._fill_rect(
                    pixels,
                    x + column_index,
                    y + row_index,
                    1,
                    1,
                    color,
                )

    def _fit_shop_cell_text(self, text: str, *, max_chars: int) -> str:
        trimmed = text.strip().upper()
        if not trimmed:
            return ""
        if len(trimmed) <= max_chars:
            return trimmed
        return trimmed[:max_chars]

    def _shop_cell_aligned_text(self, text: str, *, pad_numeric: bool = False) -> str:
        trimmed = self._fit_shop_cell_text(text, max_chars=self._SHOP_CELL_TEXT_MAX_CHARS)
        if not trimmed:
            return ""

        if pad_numeric and trimmed.isdigit():
            value = min(99, max(0, int(trimmed)))
            return f"{value:0{self._SHOP_CELL_TEXT_MAX_CHARS}d}"

        if len(trimmed) >= self._SHOP_CELL_TEXT_MAX_CHARS:
            return trimmed

        return trimmed.ljust(self._SHOP_CELL_TEXT_MAX_CHARS)

    def _shop_cell_text_x(self, cell_x: int, text: str) -> int:
        if not text:
            return cell_x
        draw_chars = min(self._SHOP_CELL_TEXT_MAX_CHARS, len(text))
        return cell_x + max(0, (self._SHOP_CELL_SIZE - (draw_chars * 8)) // 2)

    def _shop_cell_counter_text(self, row: int, column: int) -> str:
        if self._player is None:
            return ""

        if row == SHOP_ROW_WEAPONS:
            weapon_slot = column + 1
            if weapon_slot < len(self._player.weapons) and self._player.weapons[weapon_slot]:
                return "ON"
            return ""

        if row == SHOP_ROW_AMMO:
            if column >= len(self._player.bullets):
                return ""
            stock = max(0, self._player.bullets[column])
            if stock <= 0:
                return ""

            units_per_trade = max(1, bullet_shop_units_for_type(column))
            stock_packs = stock // units_per_trade
            if stock_packs < 1:
                stock_packs = 1
            stock_packs = min(99, stock_packs)
            return f"{stock_packs:02d}"

        if row == SHOP_ROW_OTHER and column == 0:
            if self._player.shield > 0:
                return f"{min(99, self._player.shield):02d}"
            return ""

        if row == SHOP_ROW_OTHER and column == 1 and self._player.target_system_enabled:
            return "ON"
        return ""

    def _shop_cell_is_locked(self, row: int, column: int) -> bool:
        if self._player is None:
            return True

        if row == SHOP_ROW_WEAPONS:
            weapon_slot = column + 1
            return weapon_slot < len(self._player.weapons) and self._player.weapons[weapon_slot]

        if row == SHOP_ROW_AMMO:
            if column >= len(self._player.bullets):
                return True
            return self._player.bullets[column] >= bullet_capacity_units_for_type(column)

        if row == SHOP_ROW_OTHER and column == 0:
            return self._player.shield >= SHOP_SHIELD_MAX_LEVEL

        if row == SHOP_ROW_OTHER and column == 1:
            return self._player.target_system_enabled

        return False

    def _shop_cell_buy_cost(self, row: int, column: int) -> int:
        if self._player is None:
            return 0

        if row == SHOP_ROW_WEAPONS:
            return weapon_shop_cost_for_slot(column + 1)

        if row == SHOP_ROW_AMMO:
            return bullet_shop_cost_for_type(column)

        if row == SHOP_ROW_OTHER and column == 0:
            return shield_shop_buy_cost_for_level(self._player.shield)

        if row == SHOP_ROW_OTHER and column == 1:
            return SHOP_TARGET_SYSTEM_COST

        return 0

    def _shop_cell_is_affordable(self, row: int, column: int) -> bool:
        if self._player is None:
            return False
        buy_cost = self._shop_cell_buy_cost(row, column)
        return buy_cost <= 0 or self._player.cash >= buy_cost

    def _shop_selection_state_color(self) -> int:
        state = self._shop_cell_state(self._shop_row, self._shop_column)
        if state == "buy":
            return self._SHOP_VALUE_COLOR
        if state == "no_cash":
            return self._SHOP_ERROR_COLOR
        return self._SHOP_MUTED_COLOR

    def _shop_cell_state(self, row: int, column: int) -> str:
        if self._player is None:
            return "locked"

        if self._shop_cell_is_locked(row, column):
            if row == SHOP_ROW_WEAPONS:
                return "owned"
            if row == SHOP_ROW_AMMO:
                return "full"
            if row == SHOP_ROW_OTHER and column == 0:
                return "max"
            if row == SHOP_ROW_OTHER and column == 1:
                return "owned"
            return "locked"

        if not self._shop_cell_is_affordable(row, column):
            return "no_cash"

        return "buy"

    def _shop_cell_visual_colors(
        self,
        row: int,
        column: int,
        *,
        selected: bool,
        selected_pulse: bool,
        state: str | None = None,
    ) -> tuple[int, int, int, int, int, int]:
        cell_state = state or self._shop_cell_state(row, column)

        fill_color = self._SHOP_SELECTED_COLOR if selected else self._SHOP_CELL_COLOR
        border_color = self._SHOP_TEXT_COLOR
        if selected:
            border_color = self._SHOP_VALUE_COLOR if selected_pulse else self._SHOP_BORDER_COLOR

        icon_color = self._SHOP_ICON_SELECTED_COLOR if selected else self._SHOP_ICON_COLOR
        label_color = self._SHOP_VALUE_COLOR if selected else self._SHOP_TEXT_COLOR
        counter_color = self._SHOP_VALUE_COLOR
        marker_color = self._SHOP_SUCCESS_COLOR

        if cell_state in ("owned", "full", "max", "locked"):
            fill_color = self._SHOP_CELL_COLOR if selected else self._SHOP_LOCKED_CELL_COLOR
            icon_color = self._SHOP_MUTED_COLOR
            label_color = self._SHOP_MUTED_COLOR
            counter_color = self._SHOP_MUTED_COLOR
            marker_color = self._SHOP_SUCCESS_COLOR
        elif cell_state == "no_cash":
            fill_color = self._SHOP_CELL_COLOR if selected else self._SHOP_UNAFFORDABLE_CELL_COLOR
            icon_color = self._SHOP_ERROR_COLOR if selected else self._SHOP_MUTED_COLOR
            label_color = self._SHOP_ERROR_COLOR if selected else self._SHOP_MUTED_COLOR
            counter_color = self._SHOP_MUTED_COLOR
            marker_color = self._SHOP_ERROR_COLOR
        elif selected and selected_pulse:
            marker_color = self._SHOP_VALUE_COLOR

        return fill_color, border_color, icon_color, label_color, counter_color, marker_color

    def _draw_gameplay_hud(self, pixels: bytearray) -> None:
        if self._player is None:
            return

        panel_x = 0
        panel_height = 28
        panel_y = SCREEN_HEIGHT - panel_height
        panel_width = SCREEN_WIDTH

        self._fill_rect(
            pixels,
            panel_x,
            panel_y,
            panel_width,
            panel_height,
            self._HUD_PANEL_COLOR,
        )
        self._fill_rect(
            pixels,
            panel_x + 1,
            panel_y + 1,
            panel_width - 2,
            10,
            self._HUD_CELL_COLOR,
        )
        self._stroke_rect(
            pixels,
            panel_x,
            panel_y,
            panel_width,
            panel_height,
            self._HUD_BORDER_COLOR,
        )

        weapon_slot = self._player.current_weapon
        weapon_name = weapon_shop_name_for_slot(weapon_slot)
        ammo_type, ammo_units, ammo_capacity = current_weapon_ammo_snapshot(self._player)
        weapon_profile = weapon_profile_for_slot(weapon_slot)

        ammo_packs = 0
        ammo_ratio = 0.0
        ammo_label = "INF"
        if ammo_type >= 0:
            units_per_pack = max(1, bullet_shop_units_for_type(ammo_type))
            ammo_packs = ammo_units // units_per_pack
            if ammo_units > 0 and ammo_packs < 1:
                ammo_packs = 1
            ammo_label = f"{ammo_packs:02d}"
            if ammo_capacity > 0:
                ammo_ratio = max(0.0, min(1.0, ammo_units / ammo_capacity))

        health_ratio = 0.0
        health_capacity = player_health_capacity(self._player)
        if health_capacity > 0.0:
            health_ratio = max(0.0, min(1.0, self._player.health / health_capacity))

        reload_ratio = 1.0
        if weapon_profile.loading_time > 0:
            reload_ratio = max(0.0, min(1.0, self._player.load_count / weapon_profile.loading_time))

        hp_color = self._HUD_OK_COLOR if health_ratio > 0.3 else self._HUD_WARN_COLOR
        am_color = self._HUD_OK_COLOR if ammo_ratio > 0.2 or ammo_type < 0 else self._HUD_WARN_COLOR
        load_color = self._HUD_OK_COLOR if reload_ratio >= 1.0 else self._HUD_TEXT_COLOR

        mines_active = 0
        mines_armed = 0
        c4_active = 0
        c4_hot = 0
        for explosive in self._player_explosives:
            if explosive.kind == "mine":
                mines_active += 1
                if explosive.arming_ticks <= 0:
                    mines_armed += 1
            elif explosive.kind == "c4":
                c4_active += 1
                if explosive.fuse_ticks <= self._C4_HOT_FUSE_TICKS:
                    c4_hot += 1

        mine_ready_ratio = 0.0
        if mines_active > 0:
            mine_ready_ratio = max(0.0, min(1.0, mines_armed / mines_active))

        c4_hot_ratio = 0.0
        if c4_active > 0:
            c4_hot_ratio = max(0.0, min(1.0, c4_hot / c4_active))

        mine_meter_color = self._HUD_OK_COLOR if mine_ready_ratio >= 1.0 else self._HUD_TEXT_COLOR
        c4_meter_color = self._HUD_WARN_COLOR if c4_hot_ratio > 0.0 else self._HUD_TEXT_COLOR

        self._draw_meter(
            pixels,
            x=4,
            y=panel_y + 2,
            width=72,
            height=4,
            ratio=health_ratio,
            fill_color=hp_color,
            border_color=self._HUD_BORDER_COLOR,
            background_color=self._HUD_CELL_COLOR,
        )
        self._draw_meter(
            pixels,
            x=80,
            y=panel_y + 2,
            width=72,
            height=4,
            ratio=ammo_ratio if ammo_type >= 0 else 1.0,
            fill_color=am_color,
            border_color=self._HUD_BORDER_COLOR,
            background_color=self._HUD_CELL_COLOR,
        )
        self._draw_meter(
            pixels,
            x=156,
            y=panel_y + 2,
            width=56,
            height=4,
            ratio=reload_ratio,
            fill_color=load_color,
            border_color=self._HUD_BORDER_COLOR,
            background_color=self._HUD_CELL_COLOR,
        )
        self._draw_meter(
            pixels,
            x=216,
            y=panel_y + 2,
            width=48,
            height=4,
            ratio=mine_ready_ratio,
            fill_color=mine_meter_color,
            border_color=self._HUD_BORDER_COLOR,
            background_color=self._HUD_CELL_COLOR,
        )
        self._draw_meter(
            pixels,
            x=268,
            y=panel_y + 2,
            width=48,
            height=4,
            ratio=c4_hot_ratio,
            fill_color=c4_meter_color,
            border_color=self._HUD_BORDER_COLOR,
            background_color=self._HUD_CELL_COLOR,
        )

        weapon_label = weapon_name.upper()
        if len(weapon_label) > 12:
            weapon_label = weapon_label[:12]

        self._draw_shop_text(
            pixels,
            4,
            panel_y + 8,
            f"W{weapon_slot:02d} {weapon_label}",
            self._HUD_VALUE_COLOR,
        )
        hp_text = f"HP {int(max(0.0, self._player.health)):03d}/{int(max(0.0, health_capacity)):03d} "
        am_text = f"AM {ammo_label}"
        ammo_text_color = am_color if ammo_type >= 0 else self._HUD_TEXT_COLOR
        self._draw_shop_text(
            pixels,
            4,
            panel_y + 18,
            hp_text,
            hp_color,
        )
        self._draw_shop_text(
            pixels,
            4 + (len(hp_text) * 8),
            panel_y + 18,
            am_text,
            ammo_text_color,
        )

        target_state = "ON" if self._player.target_system_enabled else "OFF"
        right_text = f"$ {self._player.cash} SH {self._player.shield:02d} TG {target_state}"
        right_x = max(4, SCREEN_WIDTH - ((len(right_text) + 1) * 8))
        self._draw_shop_text(
            pixels,
            right_x,
            panel_y + 8,
            right_text,
            self._HUD_VALUE_COLOR,
        )

        hint_load = f"LD {int(reload_ratio * 100):03d}% "
        hint_mine = f"M {mines_armed:02d}/{mines_active:02d} "
        hint_c4 = f"C4 {c4_hot:02d}/{c4_active:02d} "
        hint_shop = "R/ENT SHOP"
        hint_text = f"{hint_load}{hint_mine}{hint_c4}{hint_shop}"
        hint_x = max(4, SCREEN_WIDTH - ((len(hint_text) + 1) * 8))
        cursor_x = hint_x
        hint_load_color = self._HUD_OK_COLOR if reload_ratio >= 1.0 else self._HUD_TEXT_COLOR
        self._draw_shop_text(pixels, cursor_x, panel_y + 18, hint_load, hint_load_color)
        cursor_x += len(hint_load) * 8

        mine_hint_color = self._HUD_MUTED_COLOR if mines_active <= 0 else mine_meter_color
        self._draw_shop_text(pixels, cursor_x, panel_y + 18, hint_mine, mine_hint_color)
        cursor_x += len(hint_mine) * 8

        c4_hint_color = self._HUD_MUTED_COLOR if c4_active <= 0 else c4_meter_color
        self._draw_shop_text(pixels, cursor_x, panel_y + 18, hint_c4, c4_hint_color)
        cursor_x += len(hint_c4) * 8

        self._draw_shop_text(pixels, cursor_x, panel_y + 18, hint_shop, self._HUD_MUTED_COLOR)

    def _draw_meter(
        self,
        pixels: bytearray,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        ratio: float,
        fill_color: int,
        border_color: int,
        background_color: int,
    ) -> None:
        if width <= 2 or height <= 2:
            return

        self._fill_rect(pixels, x, y, width, height, background_color)
        self._stroke_rect(pixels, x, y, width, height, border_color)

        inner_width = width - 2
        inner_height = height - 2
        fill_width = int(inner_width * max(0.0, min(1.0, ratio)))
        if fill_width <= 0:
            return

        self._fill_rect(pixels, x + 1, y + 1, fill_width, inner_height, fill_color)

    def _draw_shop_text(self, pixels: bytearray, x: int, y: int, text: str, color: int) -> None:
        if not text:
            return
        if color < 0 or color > 255:
            return

        font = self._ui_font
        if font is None:
            return

        glyph_width = font.glyph_width
        glyph_height = font.glyph_height

        cursor_x = x
        for char in text:
            glyph = font.glyph(ord(char) & 0xFF)
            glyph_index = 0
            for glyph_y in range(glyph_height):
                screen_y = y + glyph_y
                if screen_y < 0 or screen_y >= SCREEN_HEIGHT:
                    glyph_index += glyph_width
                    continue

                row_offset = screen_y * SCREEN_WIDTH
                for glyph_x in range(glyph_width):
                    screen_x = cursor_x + glyph_x
                    if screen_x < 0 or screen_x >= SCREEN_WIDTH:
                        glyph_index += 1
                        continue

                    if glyph[glyph_index] > 0:
                        pixels[row_offset + screen_x] = color
                    glyph_index += 1

            cursor_x += glyph_width
            if cursor_x >= SCREEN_WIDTH:
                break

    def _fill_rect(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        color: int,
    ) -> None:
        if width <= 0 or height <= 0:
            return
        if color < 0 or color > 255:
            return

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(SCREEN_WIDTH, x + width)
        y1 = min(SCREEN_HEIGHT, y + height)
        if x0 >= x1 or y0 >= y1:
            return

        row_fill = bytes((color,)) * (x1 - x0)
        for row in range(y0, y1):
            row_start = row * SCREEN_WIDTH + x0
            pixels[row_start : row_start + (x1 - x0)] = row_fill

    def _stroke_rect(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        color: int,
    ) -> None:
        if width <= 1 or height <= 1:
            return
        self._fill_rect(pixels, x, y, width, 1, color)
        self._fill_rect(pixels, x, y + height - 1, width, 1, color)
        self._fill_rect(pixels, x, y, 1, height, color)
        self._fill_rect(pixels, x + width - 1, y, 1, height, color)

    def _resolve_pending_player_shots(self) -> None:
        if self._level is None or self._player is None:
            return

        for shot in consume_pending_shots(self._player):
            if is_player_explosive_weapon_slot(shot.weapon_slot):
                if shot.weapon_slot == 9:
                    armed_c4 = [explosive for explosive in self._player_explosives if explosive.kind == "c4"]
                    if armed_c4:
                        c4_bullet_type = weapon_bullet_type_index_for_slot(shot.weapon_slot)
                        if c4_bullet_type is not None and c4_bullet_type < len(self._player.bullets):
                            c4_capacity = bullet_capacity_units_for_type(c4_bullet_type)
                            if self._player.bullets[c4_bullet_type] < c4_capacity:
                                self._player.bullets[c4_bullet_type] += 1
                        for explosive in armed_c4:
                            explosive.fuse_ticks = 0
                        self._player.shot_effect_x = int(armed_c4[0].x)
                        self._player.shot_effect_y = int(armed_c4[0].y)
                        continue

                explosive = deploy_player_explosive_from_shot(shot)
                if explosive is None:
                    continue

                self._player_explosives.append(explosive)
                self._player.shot_effect_x = int(explosive.x)
                self._player.shot_effect_y = int(explosive.y)
                continue

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

    def _queue_shop_action(self, action: InputAction) -> None:
        if action == InputAction.MOVE_FORWARD:
            self._shop_nav_row_delta -= 1
            return
        if action == InputAction.MOVE_BACKWARD:
            self._shop_nav_row_delta += 1
            return
        if action in (InputAction.TURN_LEFT, InputAction.STRAFE_LEFT):
            self._shop_nav_column_delta -= 1
            return
        if action in (InputAction.TURN_RIGHT, InputAction.STRAFE_RIGHT):
            self._shop_nav_column_delta += 1
            return
        if action == InputAction.SHOOT:
            self._shop_buy_requested = True
            return
        if action == InputAction.NEXT_WEAPON:
            self._shop_sell_requested = True

    def _toggle_shop(self, context: GameContext) -> None:
        if self._game_over_active:
            return

        if self._shop_active:
            self._shop_active = False
            self._reset_input_flags()
            context.logger.info("Shop closed")
            return

        if not self._shop_sell_prices.weapon_slots:
            self._shop_sell_prices = generate_shop_sell_prices(
                random_seed=self._sell_seed(context),
            )

        self._shop_active = True
        self._held_actions.clear()
        self._reset_input_flags()
        self._shop_row, self._shop_column = clamp_shop_selection(self._shop_row, self._shop_column)
        context.logger.info("Shop opened row=%d col=%d", self._shop_row, self._shop_column)

    def _update_shop_state(self, context: GameContext) -> None:
        if self._player is None:
            return

        self._shop_row, self._shop_column = move_shop_selection(
            self._shop_row,
            self._shop_column,
            row_delta=self._shop_nav_row_delta,
            column_delta=self._shop_nav_column_delta,
        )

        if self._shop_buy_requested:
            event = buy_selected_shop_item(self._player, self._shop_row, self._shop_column)
            self._shop_last_transaction = event
            self._log_shop_transaction(context, event)

        if self._shop_sell_requested:
            event = sell_selected_shop_item(
                self._player,
                self._shop_row,
                self._shop_column,
                self._shop_sell_prices,
            )
            self._shop_last_transaction = event
            self._log_shop_transaction(context, event)

    def _log_shop_transaction(self, context: GameContext, event: ShopTransactionEvent) -> None:
        if self._player is None:
            return

        result = "ok" if event.success else "blocked"
        reason = event.reason if event.reason else "-"
        context.logger.info(
            "Shop %s %s row=%d col=%d units=%d cash_delta=%d cash=%d result=%s reason=%s",
            event.action,
            event.category,
            event.row,
            event.column,
            event.units,
            event.cash_delta,
            self._player.cash,
            result,
            reason,
        )

    def _activate_game_over(self, context: GameContext) -> None:
        if self._game_over_active:
            return

        self._game_over_active = True
        self._game_over_ticks_remaining = self._GAME_OVER_RETURN_TICKS
        self._shop_active = False
        self._held_actions.clear()
        self._reset_input_flags()
        self._enemy_projectiles.clear()
        self._player_explosives.clear()
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

    def _should_advance_level_progression(self) -> bool:
        if not self._progression_enabled:
            return False
        if self._player is None or self._player.dead:
            return False
        return alive_enemy_count(self._enemies) == 0

    def _advance_level_progression(self, context: GameContext) -> SceneTransition:
        from ultimatetk.ui.progression_scene import LevelCompleteScene, RunCompleteScene

        completed_level_index = context.session.level_index
        next_level_index = context.session.level_index + 1
        if self._level_exists_for_session_index(context, next_level_index):
            context.logger.info(
                "Level complete at level %d, entering level-complete scene for level %d",
                completed_level_index + 1,
                next_level_index + 1,
            )
            return SceneTransition(
                next_scene=LevelCompleteScene(
                    from_level_index=completed_level_index,
                    to_level_index=next_level_index,
                ),
            )

        context.logger.info(
            "Level complete at level %d, no next level found; entering run-complete scene",
            completed_level_index + 1,
        )
        return SceneTransition(next_scene=RunCompleteScene(completed_level_index=completed_level_index))

    def _level_exists_for_session_index(self, context: GameContext, level_index: int) -> bool:
        repo = GameDataRepository(context.paths)
        level_name = self._level_name_for_session_index(level_index)
        try:
            repo.load_lev(level_name, episode=self._DEFAULT_EPISODE)
        except (FileNotFoundError, ValueError):
            return False
        return True

    @staticmethod
    def _level_name_for_session_index(level_index: int) -> str:
        return f"LEVEL{max(1, level_index + 1)}.LEV"

    @staticmethod
    def _sell_seed(context: GameContext) -> int:
        """Deterministic seed for shop sell-price generation."""
        return (context.session.episode_index * 1000) + context.session.level_index

    def _publish_player_runtime_state(self, context: GameContext) -> None:
        if self._player is None:
            self._publish_zeroed_runtime_state(context)
            context.runtime.player_shoot_hold_active = False
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
        context.runtime.player_shoot_hold_active = self._player.shoot_hold_count > 0
        context.runtime.player_shots_fired_total = self._player.shots_fired_total
        context.runtime.player_cash = self._player.cash
        context.runtime.player_shield = self._player.shield
        context.runtime.player_target_system_enabled = self._player.target_system_enabled
        context.runtime.shop_active = self._shop_active
        context.runtime.shop_selection_row = self._shop_row
        context.runtime.shop_selection_column = self._shop_column
        if self._shop_last_transaction is None:
            self._publish_zeroed_shop_last_fields(context)
        else:
            context.runtime.shop_last_action = self._shop_last_transaction.action
            context.runtime.shop_last_category = self._shop_last_transaction.category
            context.runtime.shop_last_success = self._shop_last_transaction.success
            context.runtime.shop_last_units = self._shop_last_transaction.units
            context.runtime.shop_last_cash_delta = self._shop_last_transaction.cash_delta
            context.runtime.shop_last_reason = self._shop_last_transaction.reason
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
        mines_active = sum(1 for explosive in self._player_explosives if explosive.kind == "mine")
        mines_armed = sum(
            1 for explosive in self._player_explosives if explosive.kind == "mine" and explosive.arming_ticks <= 0
        )
        c4_active = sum(1 for explosive in self._player_explosives if explosive.kind == "c4")
        c4_hot = sum(
            1
            for explosive in self._player_explosives
            if explosive.kind == "c4" and explosive.fuse_ticks <= self._C4_HOT_FUSE_TICKS
        )
        context.runtime.player_mines_active = mines_active
        context.runtime.player_mines_armed = mines_armed
        context.runtime.player_c4_active = c4_active
        context.runtime.player_c4_hot = c4_hot
        context.runtime.player_explosives_active = mines_active + c4_active
        context.runtime.player_explosive_detonations_total = self._player_explosive_detonations
        context.runtime.game_over_active = self._game_over_active
        context.runtime.game_over_ticks_remaining = self._game_over_ticks_remaining

    def ai_state_view(self) -> GameplayStateView | None:
        if self._level is None or self._player is None:
            return None
        return GameplayStateView(
            level=self._level,
            player=self._player,
            enemies=tuple(self._enemies),
            crates=tuple(self._crates),
            enemy_projectiles=tuple(self._enemy_projectiles),
            player_explosives=tuple(self._player_explosives),
            shop_active=self._shop_active,
        )


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
