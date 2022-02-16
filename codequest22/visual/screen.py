import os
import random
import arcade
import math

from arcade.key import MOD_SHIFT
from codequest22.server import energy
from codequest22.server.ant import AntTypes
from codequest22 import stats

import codequest22.visual.constants as constants
from codequest22.visual.utils import resolve_path, hex_to_rgb
from codequest22.visual.game import CleanExit, GameStateHandler

this_dir = os.path.dirname(os.path.abspath(__file__))
f = lambda s: os.path.join(this_dir, s)

TEAM_COLORS = [
    (237, 57, 57),
    (63, 77, 237),
    (248, 218, 84),
    (31, 156, 29),
]

class AntShape:
    def __init__(self, pos, c) -> None:
        self.x, self.y = pos
        self.angle = 0
        self.shape_list = arcade.ShapeElementList()
        self.shape_list.append(arcade.create_rectangle_filled(0, 0, 2, 2, c))

    def draw(self):
        self.shape_list.center_x = self.x
        self.shape_list.center_y = self.y
        self.shape_list.angle = self.angle
        self.shape_list.draw()

class Ant(arcade.AnimatedTimeBasedSprite):

    def __init__(self, pos, c, scale=1):
        super().__init__(scale=scale)
        self.current_pos = pos
        self.new_pos = pos
        self.c_square = AntShape(pos, c)
        self.center_x, self.center_y = pos

    def update(self):
        res = super().update()
        self.c_square.x, self.c_square.y = self.center_x, self.center_y
        return res

    def update_animation(self, delta_time: float = 1 / 60):
        res = super().update_animation(delta_time=delta_time)
        if self.change_x != 0 or self.change_y != 0:
            self.stop_counter -= delta_time
            if self.stop_counter <= 0:
                self.change_x, self.change_y = 0, 0
                self.center_x, self.center_y = self.new_pos
        return res

    def set_new_pos(self, new_pos):
        self.stop_counter = GameStateHandler.get_wait_time()
        self.current_pos = self.new_pos
        self.new_pos = new_pos
        self.change_x = (self.new_pos[0] - self.current_pos[0]) / (60 * GameStateHandler.get_wait_time())
        self.change_y = (self.new_pos[1] - self.current_pos[1]) / (60 * GameStateHandler.get_wait_time())
        self.center_x, self.center_y = self.current_pos
        self.radians = math.atan2(self.change_y, self.change_x) - math.pi / 2
        self.c_square.angle = self.radians * 180 / math.pi

class GoalLine(arcade.ShapeElementList):

    def __init__(self, points):
        super().__init__()
        for p1, p2 in zip(points[:-1], points[1:]):
            self.append(arcade.create_line(p1[0], p1[1], p2[0], p2[1], (0, 0, 0), line_width=1))
        for p in points:
            self.append(arcade.create_ellipse_filled(p[0], p[1], 4, 4, (0, 255, 0)))

class ScreenManager(arcade.Window):

    instance : "ScreenManager" = None

    """General Stuff"""
    def __init__(self, width, height, title="CodeQuest", **kwargs):
        ScreenManager.instance = self
        self.vertex_list = None
        self.player_list = None
        self.s_width = width
        self.s_height = height
        super().__init__(width, height, title)
        self.scaling = min(width / 640, height / 480)
        arcade.set_background_color(hex_to_rgb(constants.GREYSCALE[-1]))
        self.setPlayableArea()
        self.ant_list = arcade.SpriteList()
        self.ant_squares = []
        # Debug Info
        self.goal_line = None
        self.goal_following = None
        self.position_info = None
        self.position_info_pane = None
        self.position_info_pane_2 = None
        self.position_info_text = []
        self.emitters = []

        self.deposit_energy_sound = arcade.load_sound("codequest22/visual/sounds/deposit_energy.wav")
        self.energy_active_sound = arcade.load_sound("codequest22/visual/sounds/energy_active.wav")
        self.energy_deactive_sound = arcade.load_sound("codequest22/visual/sounds/energy_deactive.wav")
        self.game_complete_sound = arcade.load_sound("codequest22/visual/sounds/game_complete.wav")
        self.kill_sound = arcade.load_sound("codequest22/visual/sounds/kill.wav")
        self.settler_active_sound = arcade.load_sound("codequest22/visual/sounds/settler_active.wav")
        self.settler_deactive_sound = arcade.load_sound("codequest22/visual/sounds/settler_deactive.wav")

    def spawnAnt(self, ant):

        pos = self.translate(*ant.position)
        sprite = Ant(pos, ant.color, self.scaling * 0.5)
        sprite.goal = ant.goal
        sprite.path = ant.path
        if isinstance(ant, AntTypes.get_class(AntTypes.WORKER)):
            sprite_strings = [
                f"sprites/ant/worker_proto_{ant.player_index}_0.png",
                f"sprites/ant/worker_proto_{ant.player_index}_1.png",
            ]
        elif isinstance(ant, AntTypes.get_class(AntTypes.FIGHTER)):
            sprite_strings = [
                f"sprites/ant/fighter_proto_{ant.player_index}_0.png",
                f"sprites/ant/fighter_proto_{ant.player_index}_1.png",
            ]
        elif isinstance(ant, AntTypes.get_class(AntTypes.SETTLER)):
            sprite_strings = [
                f"sprites/ant/settler_proto_{ant.player_index}_0.png",
                f"sprites/ant/settler_proto_{ant.player_index}_1.png",
            ]
        for string in sprite_strings:
            tex = arcade.load_texture(resolve_path(string))
            sprite.frames.append(arcade.AnimationKeyframe(0, 200, tex))
        sprite.texture = sprite.frames[0].texture
        self.ant_mapping[ant.player_index][ant.id] = sprite
        self.ant_list.append(sprite)
        self.ant_squares.append(sprite.c_square)

    def moveAnt(self, player_index, key, position, new_path):
        self.ant_mapping[player_index][key].set_new_pos(self.translate(*position))
        self.ant_mapping[player_index][key].path = new_path

    def removeAnt(self, player_index, key):
        self.ant_list.remove(self.ant_mapping[player_index][key])
        self.ant_squares.remove(self.ant_mapping[player_index][key].c_square)
        del self.ant_mapping[player_index][key]

    def setPlayableArea(self):
        self.L_MARG = max(50 * self.scaling, self.s_width/6) + 10 * self.scaling
        self.T_MARG = 30 * self.scaling
        self.R_MARG = 10 * self.scaling
        self.B_MARG = 10 * self.scaling
        self.PLAYABLE_WIDTH = self.s_width - self.L_MARG - self.R_MARG
        self.PLAYABLE_HEIGHT = self.s_height - self.T_MARG - self.B_MARG

    def translate(self, x, y):
        return x * self.SIDELENGTH + self.XOFFSET, -y * self.SIDELENGTH + self.YOFFSET

    def inverse_translate(self, x, y):
        return int((x - self.XOFFSET + self.SIDELENGTH/2) // self.SIDELENGTH), -1 * int((y - self.YOFFSET - self.SIDELENGTH/2) // self.SIDELENGTH)-1

    def initMap(self, map_data):
        self.map_data = map_data
        self.grid_fixes = arcade.ShapeElementList()
        self.grid_bg = arcade.SpriteList(is_static=True)
        self.after_grid = arcade.SpriteList(is_static=True)
        self.active_grid_bg = [arcade.SpriteList(is_static=True) for _ in GameStateHandler.zones]
        self.active_tile = [arcade.SpriteList(is_static=True) for _ in GameStateHandler.energy_info]

        COL_MAP = {
            ".": (16*0, 16*3),
            "R": (16*2, 16*3),
            "B": (16*3, 16*3),
            "G": (16*0, 16*4),
            "Y": (16*4, 16*3),
            "F": (16*1, 16*4),
            "W": (16*0, 16*0),
            "Z": (16*3, 16*6),
        }
        self.SIDELENGTH = min(self.PLAYABLE_WIDTH / len(self.map_data[0]), self.PLAYABLE_HEIGHT / len(self.map_data))
        self.XOFFSET = self.L_MARG + (self.PLAYABLE_WIDTH - self.SIDELENGTH * len(self.map_data[0])) / 2 + self.SIDELENGTH / 2
        self.YOFFSET = self.s_height - self.T_MARG - (self.PLAYABLE_HEIGHT - self.SIDELENGTH * len(self.map_data)) / 2 - self.SIDELENGTH / 2

        zoned = [[False for __ in range(len(self.map_data[0]))] for _ in range(len(self.map_data))]

        for y in range(len(self.map_data)):
            for x in range(len(self.map_data[y])):
                c = self.map_data[y][x]
                a, b = None, None
                before = []
                extra = []
                capture = False
                cx, cy = self.translate(x, y)
                if c == ".":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                elif c == "R":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                    self.after_grid.append(arcade.Sprite(
                        "codequest22/visual/sprites/red-base.png",
                        center_x = cx,
                        center_y = cy,
                        scale = self.scaling * 24/512
                    ))
                elif c == "B":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                    self.after_grid.append(arcade.Sprite(
                        "codequest22/visual/sprites/blue-base.png",
                        center_x = cx,
                        center_y = cy,
                        scale = self.scaling * 24/512
                    ))
                elif c == "Y":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                    self.after_grid.append(arcade.Sprite(
                        "codequest22/visual/sprites/yellow-base.png",
                        center_x = cx,
                        center_y = cy,
                        scale = self.scaling * 24/512
                    ))
                elif c == "G":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                    self.after_grid.append(arcade.Sprite(
                        "codequest22/visual/sprites/green-base.png",
                        center_x = cx,
                        center_y = cy,
                        scale = self.scaling * 24/512
                    ))
                elif c == "W":
                    before.append(random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ]))
                    # Match some tile.
                    # Match is TL, T, TR, R, BR, B, BL, L
                    water_map = {
                        # 3 Walls
                        "A.AWAWAW": (17*1, 17*0),
                        "AWA.AWAW": (17*2, 17*0),
                        "AWAWAWA.": (17*1, 17*1),
                        "AWAWA.AW": (17*2, 17*1),
                        # Corner bits
                        "AWAW.WAW": (17*1, 17*2),
                        "AWAWAW.W": (17*2, 17*2),
                        "AW.WAWAW": (17*1, 17*3),
                        ".WAWAWAW": (17*2, 17*3),
                        # Path endings
                        "AWA.A.A.": (17*1, 17*4),
                        "A.A.AWA.": (17*2, 17*4),
                        "A.A.A.AW": (17*1, 17*5),
                        "A.AWA.A.": (17*2, 17*5),
                        # Path Turns
                        "A.AW.WA.": (17*3, 17*0),
                        "A.A.AW.W": (17*4, 17*0),
                        "AW.WA.A.": (17*3, 17*1),
                        ".WA.A.AW": (17*4, 17*1),
                        # Paths
                        "AWA.AWA.": (17*5, 17*0),
                        "A.AWA.AW": (17*5, 17*1),
                        # Crossroads
                        ".W.W.W.W": (17*3, 17*5),
                        # By itself
                        "A.A.A.A.": (17*4, 17*5),
                        # Nine patch
                        "A.AWWWA.": (17*3, 17*2),
                        "A.A.AWWW": (17*5, 17*2),
                        "AWWWA.A.": (17*3, 17*4),
                        "WWA.A.AW": (17*5, 17*4),
                        "A.AWWWWW": (17*4, 17*2),
                        "AWWWWWA.": (17*3, 17*3),
                        "WWA.AWWW": (17*5, 17*3),
                        "WWWWA.AW": (17*4, 17*4),
                        "WWWWWWWW": (17*4, 17*3),
                    }
                    points = [(y-1, x-1), (y-1, x), (y-1, x+1), (y, x+1), (y+1, x+1), (y+1, x), (y+1, x-1), (y, x-1)]
                    for key in water_map:
                        bad = False
                        for i2, (z, w) in enumerate(points):
                            if not (0 <= z < len(self.map_data) and 0 <= w < len(self.map_data[0])):
                                if key[i2] in "WA": continue
                                bad = True
                                break
                            c2 = self.map_data[z][w]
                            if key[i2] == "W":
                                if c2 in ".RBYGPZ":
                                    bad = True
                                    break
                            if key[i2] == ".":
                                if c2 in "W":
                                    bad = True
                                    break
                        if not bad:
                            a, b = water_map[key]
                    if a == None:
                        # Fallback, show errors.
                        a, b = (9*17, 3*17)
                elif c == "F":
                    a, b = random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ])
                    self.after_grid.append(arcade.Sprite(
                        "codequest22/visual/sprites/normal.png",
                        center_x = cx,
                        center_y = cy,
                        scale = self.scaling * 16/512
                    ))
                    for i2, t in enumerate(GameStateHandler.energy_info):
                        if t.position == (y, x):
                            self.active_tile[i2].append(arcade.Sprite(
                                "codequest22/visual/sprites/super.png",
                                center_x = cx,
                                center_y = cy,
                                scale = self.scaling * 16/512
                            ))
                            break
                    else:
                        raise ValueError("Map loading failed...")
                    found = False
                    for z, w in [(y+1, x), (y-1, x), (y, x+1), (y, x-1)]:
                        if 0 <= z < len(self.map_data) and 0 <= w < len(self.map_data[0]):
                            if self.map_data[z][w] == "Z":
                                found = True
                    zoned[y][x] = found
                    if not found:
                        a, b = random.choice([
                            (17*0, 17*0),
                            (17*0, 17*1),
                        ])
                if a == None:
                    capture = True
                    # We are a capture zone
                    before.append(random.choice([
                        (17*0, 17*0),
                        (17*0, 17*1),
                    ]))
                    # Match some tile.
                    # Match is TL, T, TR, R, BR, B, BL, L
                    zone_map = {
                        # 3 Walls
                        "A.AWAWAW": (17*6, 17*0),
                        "AWA.AWAW": (17*7, 17*0),
                        "AWAWAWA.": (17*6, 17*1),
                        "AWAWA.AW": (17*7, 17*1),
                        # Corner bits
                        "AWAW.WAW": (17*6, 17*2),
                        "AWAWAW.W": (17*7, 17*2),
                        "AW.WAWAW": (17*6, 17*3),
                        ".WAWAWAW": (17*7, 17*3),
                        # Path endings
                        "AWA.A.A.": (17*6, 17*4),
                        "A.A.AWA.": (17*7, 17*4),
                        "A.A.A.AW": (17*6, 17*5),
                        "A.AWA.A.": (17*7, 17*5),
                        # Path Turns
                        "A.AW.WA.": (17*8, 17*0),
                        "A.A.AW.W": (17*9, 17*0),
                        "AW.WA.A.": (17*8, 17*1),
                        ".WA.A.AW": (17*9, 17*1),
                        # Paths
                        "AWA.AWA.": (17*9, 17*0),
                        "A.AWA.AW": (17*9, 17*1),
                        # Crossroads
                        ".W.W.W.W": (17*8, 17*5),
                        # By itself
                        "A.A.A.A.": (17*9, 17*5),
                        # Nine patch
                        "A.AWWWA.": (17*8, 17*2),
                        "A.A.AWWW": (17*10, 17*2),
                        "AWWWA.A.": (17*8, 17*4),
                        "WWA.A.AW": (17*10, 17*4),
                        "A.AWWWWW": (17*9, 17*2),
                        "AWWWWWA.": (17*8, 17*3),
                        "WWA.AWWW": (17*10, 17*3),
                        "WWWWA.AW": (17*9, 17*4),
                        "WWWWWWWW": (17*9, 17*3),
                    }
                    points = [(y-1, x-1), (y-1, x), (y-1, x+1), (y, x+1), (y+1, x+1), (y+1, x), (y+1, x-1), (y, x-1)]
                    for key in zone_map:
                        bad = False
                        for i2, (z, w) in enumerate(points):
                            if not (0 <= z < len(self.map_data) and 0 <= w < len(self.map_data[0])):
                                if key[i2] in "WA": continue
                                bad = True
                                break
                            c2 = self.map_data[z][w]
                            if key[i2] == "W":
                                if c2 in ".RBYGW":
                                    bad = True
                                    break
                            if key[i2] == ".":
                                if c2 in "ZF":
                                    bad = True
                                    break
                        if not bad:
                            a, b = zone_map[key]
                    if a == None:
                        # Fallback, show errors.
                        a, b = (4*17, 3*17)
                for p, l in before:
                    s = arcade.Sprite(
                        "codequest22/visual/sprites/full_tileset.png", 
                        image_x=p, 
                        image_y=l, 
                        image_width=16, 
                        image_height=16, 
                        center_x=cx, 
                        center_y=cy,
                        scale=self.SIDELENGTH / 16,
                    )
                    self.grid_bg.append(s)
                s = arcade.Sprite(
                    "codequest22/visual/sprites/full_tileset.png", 
                    image_x=a, 
                    image_y=b, 
                    image_width=16, 
                    image_height=16, 
                    center_x=cx, 
                    center_y=cy,
                    scale=self.SIDELENGTH / 16,
                )
                self.grid_bg.append(s)
                if capture:
                    for i in range(len(GameStateHandler.zones)):
                        if (y, x) in GameStateHandler.zones[i]:
                            s2 = arcade.Sprite(
                                "codequest22/visual/sprites/full_tileset.png", 
                                image_x=a, 
                                image_y=b + 6*17, 
                                image_width=16, 
                                image_height=16, 
                                center_x=cx, 
                                center_y=cy,
                                scale=self.SIDELENGTH / 16,
                            )
                            self.active_grid_bg[i].append(s2)
                for p, l in extra:
                    s = arcade.Sprite(
                        "codequest22/visual/sprites/full_tileset.png", 
                        image_x=p, 
                        image_y=l, 
                        image_width=16, 
                        image_height=16, 
                        center_x=cx, 
                        center_y=cy,
                        scale=self.SIDELENGTH / 16,
                    )
                    self.after_grid.append(s)
        for y in range(1, len(self.map_data)):
            for x in range(1, len(self.map_data[y])):
                # Am I the bottom right of a square of walls/zones? If so then add a little square to hide the bad stuff.
                if self.map_data[y][x] == "W":
                    for a, b in [(y-1, x), (y-1, x-1), (y, x-1)]:
                        if self.map_data[a][b] != "W":
                            break
                    else:
                        px, py = self.translate(x, y)
                        self.grid_fixes.append(arcade.create_rectangle_filled(px-self.SIDELENGTH/2, py+self.SIDELENGTH/2, self.SIDELENGTH*.45, self.SIDELENGTH*.45, (168, 182, 183)))
                if self.map_data[y][x] == "Z" or (self.map_data[y][x] == "F" and zoned[y][x]):
                    for a, b in [(y-1, x), (y-1, x-1), (y, x-1)]:
                        if not (
                            self.map_data[a][b] == "Z" or
                            (self.map_data[a][b] == "F" and zoned[a][b])
                        ):
                            break
                    else:
                        px, py = self.translate(x, y)
                        self.grid_fixes.append(arcade.create_rectangle_filled(px-self.SIDELENGTH/2, py+self.SIDELENGTH/2, self.SIDELENGTH*.45, self.SIDELENGTH*.45, (230, 218, 191)))

    def initPlayers(self, images):
        self.setup_player_ui_main(len(images))
        self.player_list = arcade.SpriteList()
        self.ui_player_list = arcade.SpriteList(is_static=True)
        self.ui_player_list_hill_icon = arcade.SpriteList(is_static=True)
        self.ui_player_list_energy_icon = arcade.SpriteList(is_static=True)
        self.ant_mapping = [{} for _ in range(len(images))]
        names = ["red", "blue", "yellow", "green"]
        for x, image in enumerate(images):
            spritepath = resolve_path(image, "test_bots/img/hello.png")
            # UI
            ui_sprite = arcade.Sprite(spritepath, scale=self.scaling)
            ratio = ui_sprite.width / ui_sprite.height
            ui_sprite.height = self.player_sprite_height
            ui_sprite.width = ui_sprite.height * ratio
            ui_sprite.center_x = self.player_ui_main_top_left[x][0] + self.player_ui_main_width / 2
            ui_sprite.center_y = self.player_ui_main_top_left[x][1] - self.player_sprite_height / 2
            hill = arcade.Sprite(f"codequest22/visual/sprites/{names[x]}-base.png", 
                center_x=self.player_ui_main_top_left[x][0] + 10 * self.scaling, 
                center_y=self.player_ui_main_top_left[x][1] - self.panel_height * 0.64,
                scale=self.scaling * 16/512,
            )
            energy = arcade.Sprite("codequest22/visual/sprites/full_tileset.png", 
                image_x=0, 
                image_y=17*6, 
                image_width=16, 
                image_height=16, 
                center_x=self.player_ui_main_top_left[x][0] + 10 * self.scaling, 
                center_y=self.player_ui_main_top_left[x][1] - self.panel_height * 0.84,
                scale=self.scaling,
            )
            self.ui_player_list.append(ui_sprite)
            self.ui_player_list_hill_icon.append(hill)
            self.ui_player_list_energy_icon.append(energy)

    def collectEnergyAnimation(self, player_index, ant_id):
        position = self.ant_mapping[player_index][ant_id].new_pos
        self.emitters.append(arcade.Emitter(
            center_xy=position,
            emit_controller=arcade.EmitBurst(3),
            particle_factory=lambda emitter: arcade.FadeParticle(
                filename_or_texture="codequest22/visual/sprites/energy_particle.png",
                change_xy=arcade.rand_in_circle((0.0, 0.0), 1),
                lifetime=random.uniform(0.3, 0.6),
                scale=2,
                start_alpha=80,
                end_alpha=0
            )
        ))

    def killAnimation(self, player_index, ant_id, old_age):
        position = self.ant_mapping[player_index][ant_id].new_pos
        self.emitters.append(arcade.Emitter(
            center_xy=position,
            emit_controller=arcade.EmitBurst(3),
            particle_factory=lambda emitter: arcade.FadeParticle(
                filename_or_texture="codequest22/visual/sprites/old_age_particle.png" if old_age else "codequest22/visual/sprites/dead_particle.png",
                change_xy=arcade.rand_in_circle((0.0, 0.0), 1),
                lifetime=random.uniform(0.3, 0.6),
                scale=2,
                start_alpha=80,
                end_alpha=0
            )
        ))
        if not old_age:
            arcade.play_sound(self.kill_sound, 0.1, 0, False)

    def playDepositSound(self):
        arcade.play_sound(self.deposit_energy_sound, 0.01, 0, False)

    def playEnergyActiveSound(self):
        arcade.play_sound(self.energy_active_sound, 0.02, 0, False)
    
    def playEnergyDeactiveSound(self):
        arcade.play_sound(self.energy_deactive_sound, 0.02, 0, False)
    
    def playZoneActiveSound(self):
        arcade.play_sound(self.settler_active_sound, 0.1, 0, False)
    
    def playZoneDeactiveSound(self):
        arcade.play_sound(self.settler_deactive_sound, 0.1, 0, False)
    
    def playGameCompleteSound(self):
        arcade.play_sound(self.game_complete_sound, 0.5, 0, False)

    def on_update(self, delta_time: float):
        super().on_update(delta_time)
        if self.ant_list is not None:
            self.ant_list.update()
            for v in self.ant_list:
                v.update_animation(delta_time)
        if self.player_list is not None:
            self.player_list.update()
        if self.goal_following is not None:
            try:
                ant = self.ant_mapping[self.goal_following[0]][self.goal_following[1]]
                self.goal_line = GoalLine(
                    [
                        self.translate(p[1], p[0])
                        for p in ant.path
                    ] + [(ant.center_x, ant.center_y)]
                )
            except Exception as e:
                self.goal_following = None
                self.goal_line = None
        else:
            self.goal_line = None
        to_remove = []
        for i, emitter in enumerate(self.emitters):
            emitter.update()
            if emitter.can_reap():
                to_remove.append(i)
        for idx in to_remove[::-1]:
            del self.emitters[idx]
        if self.position_info is not None:
            px, py = self.translate(*self.position_info)
            t = self.map_data[self.position_info[1]][self.position_info[0]]
            if t == "P":
                tp = tuple(self.position_info[::-1])
                for tile in GameStateHandler.energy_info:
                    if tile.position == tp:
                        text = [
                            f"Production: {tile.amount}"
                        ]
                        break
                else:
                    tile = []
            elif t == "W":
                text = [
                    "Not Traversable"
                ]
            elif t in "RBYG":
                idx = "RBYG".index(t)
                name = ["Red", "Blue", "Yellow", "Green"]
                energy = 0 if idx >= len(GameStateHandler.energy) else GameStateHandler.energy[idx]
                text = [
                    f"{name[idx]} Spawn",
                    f"{energy} Energy"
                ]
            elif t == ".":
                text = [
                    "Traversable"
                ]
            elif t == "Z":
                tp = tuple(self.position_info[::-1])
                for i in range(len(GameStateHandler.zones)):
                    if tp in GameStateHandler.zones[i]:
                        active = GameStateHandler.active_zones[i]
                        break
                else:
                    active = False
                active = "Active" if active else "Not Active"
                text = [
                    f"Hill ({active})"
                ]
            else:
                text = []
            cx, cy = px, py
            if px < self.s_width / 2:
                cx = px + 65 * self.scaling
            else:
                cx = px - 65 * self.scaling
            if py < self.s_height / 2:
                cy = py + 10 * self.scaling * len(text)
            else:
                cy = py - 10 * self.scaling * len(text)
            self.position_info_pane = arcade.create_rectangle_filled(cx, cy, 130 * self.scaling, 20 * self.scaling * len(text), (100, 100, 100, 180))
            self.position_info_pane_2 = arcade.create_rectangle_outline(cx, cy, 130 * self.scaling, 20 * self.scaling * len(text), (150, 150, 150), 1 * self.scaling)
            mid = (len(text)-1) / 2
            self.position_info_text = [
                ((cx - 60 * self.scaling, cy - 5 * self.scaling - 20 * (i - mid) * self.scaling), text[i])
                for i in range(len(text))
            ]
        GameStateHandler.tick(delta_time)

    def on_draw(self):
        arcade.start_render()
        if self.grid_bg is not None:
            self.grid_bg.draw()
        for i in range(len(GameStateHandler.active_zones)):
            if GameStateHandler.active_zones[i]:
                self.active_grid_bg[i].draw()
        if self.grid_fixes is not None:
            self.grid_fixes.draw()
        if self.after_grid is not None:
            self.after_grid.draw()
        for i in range(len(GameStateHandler.active_tiles)):
            if GameStateHandler.active_tiles[i]:
                self.active_tile[i].draw()
        if self.player_list is not None:
            self.player_list.draw()
        if self.ant_list is not None:
            self.ant_list.draw()
        if self.ant_squares is not None:
            for sq in self.ant_squares:
                sq.draw()
        for emitter in self.emitters:
            emitter.draw()
        if self.goal_line is not None:
            self.goal_line.draw()
        if self.position_info is not None:
            if self.position_info_pane is not None:
                self.position_info_pane.draw() 
                self.position_info_pane_2.draw() 
            for (px, py), line in self.position_info_text:
                arcade.draw_text(line, px, py, font_size=10 * self.scaling, font_name="codequest22/visual/fonts/Montserrat/Montserrat-Light.ttf", color=(255, 255, 255))
        self.draw_player_ui_main(GameStateHandler.hill, GameStateHandler.energy, GameStateHandler.health)

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.ESCAPE:
            arcade.close_window()
        if symbol == arcade.key.P:
            GameStateHandler.toggleMode()
        if symbol == arcade.key.O:
            GameStateHandler.stepExecution()
        if symbol == arcade.key.F:
            idx = -1 if (modifiers & arcade.key.MOD_SHIFT) else 0
            self.set_fullscreen(not self.fullscreen, arcade.get_screens()[idx])
            self.set_viewport(0, self.s_width, 0, self.s_height)
        if symbol == arcade.key.I:
            GameStateHandler.SPEED_MODE = "SUPER_SLOW" if (modifiers & arcade.key.MOD_SHIFT) else "SLOW"
        if symbol == arcade.key.O:
            GameStateHandler.SPEED_MODE = "SUPER_FAST" if (modifiers & arcade.key.MOD_SHIFT) else "FAST"

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.I:
            if GameStateHandler.SPEED_MODE in ("SLOW", "SUPER_SLOW"):
                GameStateHandler.SPEED_MODE = "NORMAL"
        if symbol == arcade.key.O:
            if GameStateHandler.SPEED_MODE in ("FAST", "SUPER_FAST"):
                GameStateHandler.SPEED_MODE = "NORMAL"

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        gx, gy = self.inverse_translate(x, y)
        if 0 <= gx < len(self.map_data[0]) and 0 <= gy < len(self.map_data):
            if button == arcade.MOUSE_BUTTON_LEFT:
                # Hide any position info
                self.position_info = None
                # Show goal info
                self.goal_following = None
                best = None
                ant_id = None
                for pid in range(len(self.ant_mapping)):
                    for key in self.ant_mapping[pid]:
                        ant = self.ant_mapping[pid][key]
                        d = abs(x - ant.center_x) + abs(y - ant.center_y)
                        if best is None or d < best:
                            best = d
                            ant_id = (pid, key)
                if best is not None and best < 15 * self.scaling:
                    self.goal_following = ant_id
            elif button == arcade.MOUSE_BUTTON_RIGHT:
                # Hide any goals
                self.goal_following = None
                self.goal_line = None
                # Show position info
                self.position_info = round(gx), round(gy)

    """UI Components"""
    def setup_player_ui_main(self, n_players):
        self.PLAYER_UI_MAIN_Y_MARGIN = 30 * self.scaling
        self.PLAYER_UI_MAIN_X_MARGIN = 10 * self.scaling
        base_height = 160 * self.scaling
        m1 = max(1, n_players - 1)
        self.player_ui_main_width = max(50 * self.scaling, self.s_width/6) - self.PLAYER_UI_MAIN_X_MARGIN
        self.top_ui_size = min(self.s_height * 0.8, base_height * n_players + 15 * m1 * self.scaling)
        self.panel_margins = max(10 * self.scaling, (self.top_ui_size - base_height * n_players) / m1)
        self.panel_height = (self.top_ui_size - self.panel_margins * m1) / n_players
        self.player_ui_main_shapes = arcade.ShapeElementList()
        self.player_ui_main_top_left = [
            (self.PLAYER_UI_MAIN_X_MARGIN, self.s_height - self.PLAYER_UI_MAIN_Y_MARGIN - (self.panel_height + self.panel_margins) * x)
            for x in range(n_players)
        ]
        self.player_sprite_height = self.panel_height / 2
        for x in range(n_players):
            self.player_ui_main_shapes.append(arcade.create_rectangle_filled(
                self.player_ui_main_top_left[x][0] + self.player_ui_main_width / 2,
                self.player_ui_main_top_left[x][1] - self.panel_height / 2,
                self.player_ui_main_width,
                self.panel_height,
                (150, 150, 150, 80)
            ))
            self.player_ui_main_shapes.append(arcade.create_line_strip(
                (
                    (self.player_ui_main_top_left[x][0] + self.player_ui_main_width - self.scaling, self.player_ui_main_top_left[x][1]), 
                    (self.player_ui_main_top_left[x][0] + self.player_ui_main_width - self.scaling, self.player_ui_main_top_left[x][1] - self.panel_height)
                ), 
                (255, 255, 255, 255), 
                line_width=2,
            ))
            self.player_ui_main_shapes.append(arcade.create_rectangle_filled(
                self.player_ui_main_top_left[x][0] + self.player_ui_main_width / 2 - self.scaling,
                self.player_ui_main_top_left[x][1] - self.panel_height + self.scaling * 2,
                self.player_ui_main_width - 2 * self.scaling,
                self.scaling * 4,
                (255, 0, 0, 255)
            ))
        self.duration_backing_bar = arcade.create_rectangle_filled(self.L_MARG + self.PLAYABLE_WIDTH / 2, self.s_height - 5 * self.scaling - (self.T_MARG - 10 * self.scaling) /2, self.PLAYABLE_WIDTH * 0.9, (self.T_MARG - 10 * self.scaling), (10, 10, 10))
        self.show_winner = False

    def draw_player_ui_main(self, hill, energy, health):
        self.player_ui_main_shapes.draw()
        self.ui_player_list.draw()
        for x in range(len(energy)):
            arcade.draw_text(str(hill[x]), self.player_ui_main_top_left[x][0] + 23 * self.scaling, self.player_ui_main_top_left[x][1] - self.panel_height*0.70, font_size=14 * self.scaling, font_name="codequest22/visual/fonts/Montserrat/Montserrat-Light.ttf")
            arcade.draw_text(str(energy[x]), self.player_ui_main_top_left[x][0] + 23 * self.scaling, self.player_ui_main_top_left[x][1] - self.panel_height*0.93, font_size=14 * self.scaling, font_name="codequest22/visual/fonts/Montserrat/Montserrat-Light.ttf")
            pct = health[x] / stats.general.QUEEN_HEALTH
            total_width = self.player_ui_main_width - 2 * self.scaling
            arcade.draw_rectangle_filled(
                self.player_ui_main_top_left[x][0] + self.player_ui_main_width / 2 - self.scaling - total_width * (1 - pct) / 2,
                self.player_ui_main_top_left[x][1] - self.panel_height + self.scaling * 2,
                total_width * pct,
                self.scaling * 4,
                (0, 255, 0, 255)
            )
        self.ui_player_list_hill_icon.draw()
        self.ui_player_list_energy_icon.draw()
        self.duration_backing_bar.draw()
        if GameStateHandler.cur_tick == 0:
            arcade.draw_text("Waiting for precomputation", self.L_MARG + self.PLAYABLE_WIDTH * 0.125, self.s_height - 5 * self.scaling - (self.T_MARG - 10 * self.scaling) /2, font_size=14 * self.scaling, font_name="codequest22/visual/fonts/Montserrat/Montserrat-Light.ttf", align="center", width=self.PLAYABLE_WIDTH * 0.75, anchor_y="center")
        else:
            dist = GameStateHandler.cur_tick / stats.general.SIMULATION_TICKS
            total = sum(GameStateHandler.hill)
            base_line = max(0, min(total//4 -1, min(GameStateHandler.hill) - 0.25 * (max(GameStateHandler.hill) - min(GameStateHandler.hill))))
            vals = GameStateHandler.hill
            if total == 0:
                total = len(GameStateHandler.hill)
                vals = [1]*len(GameStateHandler.hill)
                base_line = 0
            else:
                total -= base_line * len(GameStateHandler.hill)
            base_color = [0, 0, 0, 255]
            for i in range(len(vals)):
                for x in range(3):
                    base_color[x] += TEAM_COLORS[i][x] * ((vals[i] - base_line) / total)
            arcade.draw_rectangle_filled(self.L_MARG + self.PLAYABLE_WIDTH * 0.05 + self.PLAYABLE_WIDTH * 0.45 * dist, self.s_height - 5 * self.scaling - (self.T_MARG - 10 * self.scaling) /2, self.PLAYABLE_WIDTH * 0.9 * dist, (self.T_MARG - 10 * self.scaling), base_color)
            arcade.draw_text(f"{GameStateHandler.cur_tick}/{stats.general.SIMULATION_TICKS}", self.L_MARG + self.PLAYABLE_WIDTH * 0.125, self.s_height - 5 * self.scaling - (self.T_MARG - 10 * self.scaling) /2, font_size=14 * self.scaling, font_name="codequest22/visual/fonts/Montserrat/Montserrat-Light.ttf", align="center", width=self.PLAYABLE_WIDTH * 0.75, anchor_y="center")
        if self.show_winner:
            self.winner_bg.draw()
            arcade.draw_text(
                self.winner_text, 
                self.s_width/2,
                self.s_height/2 - 100 * self.scaling,
                font_size = self.scaling * 12,
                anchor_x = "center",
            )
            self.winner_graph_bg.draw()
            for line in self.winner_lines:
                line.draw()

    def show_winner_ui(self, indicies):
        self.show_winner = True
        self.winner_bg = arcade.create_rectangle(
            self.s_width/2, 
            self.s_height/2, 
            240 * self.scaling, 
            240 * self.scaling, 
            (50, 50, 50, 180)
        )
        name_index = ["Red", "Blue", "Yellow", "Green"]
        names = [name_index[i] for i in indicies]
        if len(names) == 0:
            self.winner_text = "Draw!"
        elif len(names) == 1:
            self.winner_text = f"{names[0]} Won!"
        else:
            self.winner_text = f"{' and '.join(names)} Won!"
        # Graph
        self.winner_graph_bg = arcade.create_rectangle(
            self.s_width/2,
            self.s_height/2 + 20 * self.scaling,
            180 * self.scaling,
            160 * self.scaling,
            (50, 50, 50, 230)
        )
        max_hill = max(GameStateHandler.hill)
        # graph is from 0 to max_hill + 10%
        max_hill = max(10, max_hill) * 1.1
        self.winner_lines = [arcade.ShapeElementList() for _ in GameStateHandler.hill]
        for i in range(len(GameStateHandler.hill_snapshots)):
            for j in range(len(GameStateHandler.hill_snapshots[i])):
                cx = self.s_width/2 - 80 * self.scaling + (i / len(GameStateHandler.hill_snapshots)) * 160 * self.scaling
                cy = self.s_height/2 - 50 * self.scaling + (GameStateHandler.hill_snapshots[i][j] / max_hill) * 140 * self.scaling
                self.winner_lines[j].append(arcade.create_ellipse_filled(
                    cx, cy, self.scaling*2, self.scaling*2, TEAM_COLORS[j], num_segments=64,
                ))
