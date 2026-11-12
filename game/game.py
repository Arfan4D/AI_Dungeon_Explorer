"""Main game controller: window, input, animation and rendering."""
import csv
import math
import os
import random
import time

import pygame

from . import settings as S
from .dungeon import (HEURISTIC_LABELS, HEURISTICS, Dungeon, is_solvable,
                      random_dungeon)
from .graphics import Particles, draw_chest, draw_explorer, draw_key, draw_star
from .levels import LEVELS
from .paths import app_dir
from .screens import BenchmarkScreen, RaceScreen
from .search import (ALGORITHM_ORDER, FAILURE, FULL_NAMES, INFO, INFORMED, QUEUE_RULE,
                     SUCCESS, UNINFORMED, run_algorithm)
from .sound import Sound
from .ui import Button, Dashboard, Row, draw_text, wrap_text

COL = S.COLORS
BASE_DIR = app_dir()
RESULTS_DIR = os.path.join(BASE_DIR, "results")
SHOT_DIR = os.path.join(BASE_DIR, "screenshots")

MOVE_KEYS = {
    pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0),
    pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
    pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1),
    pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1),
}

BUTTON_LABELS = {"BFS": "BFS", "DFS": "DFS", "UCS": "UCS", "DLS": "DLS", "IDS": "IDS",
                 "Greedy": "Greedy Best-First", "A*": "A* Search"}

TERRAIN_NAMES = {S.WALL: "Wall", S.FLOOR: "Floor (cost 1)", S.MUD: "Mud (cost 3)", S.WATER: "Water (cost 5)"}
BOX_Y, BOX_H = 488, 122          # stats / editor box inside the side panel


def num(x):
    """Compact number formatting for g / h / f values."""
    text = f"{x:.1f}"
    return text[:-2] if text.endswith(".0") else text


BRUSHES = [("Wall", "wall"), ("Floor", "floor"), ("Mud", "mud"), ("Water", "water"),
           ("Start", "start"), ("Key", "key"), ("Treasure", "goal")]

HELP_LINES = [
    ("1 - 7", "Choose algorithm (BFS, DFS, UCS, DLS, IDS, Greedy, A*)"),
    ("Space / Enter", "Run the selected algorithm"),
    ("P", "Pause / resume the animation"),
    ("F", "Step: expand ONE node at a time (great for explaining)"),
    ("R", "Reset the current run"),
    ("M", "Switch AI Solver  <->  Manual Play"),
    ("Arrows / WASD", "Move in manual mode (hold to keep walking)"),
    ("Backspace / Z", "Undo the last manual move"),
    ("T", "Hint: shows the A* optimal route from where you stand"),
    ("H", "Cycle the heuristic used by Greedy and A*"),
    ("- / =", "Depth limit of DLS  -5 / +5"),
    (", / .", "Animation speed slower / faster"),
    ("[ / ]", "Previous / next level"),
    ("N", "Generate a new random (always solvable) dungeon"),
    ("E", "Map editor: paint walls, mud, water; move start, key, treasure"),
    ("C", "Comparison dashboard (algorithms + heuristic study)"),
    ("I", "Inspector: queue panel + hover any cell for g / h / f and its parent"),
    ("V", "Algorithm Race: 2-4 algorithms solve the same map side by side"),
    ("B", "Benchmark: all algorithms on 10-100 random maps, averaged"),
    ("X", "Sound on / off"),
    ("F12", "Save a screenshot to the screenshots folder"),
    ("Esc", "Quit  (inside editor / dashboard: close it)"),
]


class Game:
    def __init__(self):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512)
        except Exception:
            pass
        pygame.init()
        pygame.display.set_caption("AI Dungeon Explorer: The Lost Temple")
        self.screen = pygame.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.rect(icon, (24, 20, 40), (0, 0, 32, 32), border_radius=7)
            draw_explorer(icon, (16, 16), 44, True)
            pygame.display.set_icon(icon)
        except Exception:
            pass
        self.clock = pygame.time.Clock()
        self.move_cooldown = 0.0             # lets the player hold a key to keep walking
        self.sound = Sound()

        names = "segoeui,dejavusans,arial,helvetica"
        self.fonts = {
            "tiny": pygame.font.SysFont(names, 12, bold=True),
            "small": pygame.font.SysFont(names, 15),
            "normal": pygame.font.SysFont(names, 17),
            "big": pygame.font.SysFont(names, 24, bold=True),
            "sub": pygame.font.SysFont(names, 30),
            "title": pygame.font.SysFont(names, 60, bold=True),
        }

        self.grid_rect = pygame.Rect(S.GRID_AREA)
        self.status_rect = pygame.Rect(S.STATUS_AREA)
        self.chart_rect = pygame.Rect(S.CHART_AREA)
        self.panel_rect = pygame.Rect(S.PANEL_AREA)
        self.dashboard = Dashboard((40, 24, S.WINDOW_W - 80, S.WINDOW_H - 48))

        # --- user settings
        self.state = "title"                 # "title" or "play"
        self.algorithm = "A*"
        self.depth_limit = S.DEFAULT_DEPTH_LIMIT
        self.heuristic_index = 0
        self.speed_index = 3
        self.mode = "ai"                     # "ai" or "manual"
        self.level_index = 0
        self.is_random = False
        self.is_custom = False
        self.editing = False
        self.brush = "wall"
        self.editor_valid = True
        self.show_dashboard = False
        self.show_help = False
        self.running = True
        self.time = 0.0
        self.particles = Particles()
        self.banner = None
        self._last_blip = 0

        self.show_inspector = False
        self.race_screen = RaceScreen(self.fonts, self.sound, self.render_map)
        self.bench_screen = BenchmarkScreen(self.fonts, self.sound, RESULTS_DIR)

        self.dungeon = LEVELS[0]
        self.buttons = []
        self.editor_buttons = []
        self._build_buttons()
        self.load_dungeon(LEVELS[0])

    # ================================================================
    #  Level handling
    # ================================================================
    def load_dungeon(self, dungeon: Dungeon):
        self.editing = False
        self.dungeon = dungeon
        self.cell = min(self.grid_rect.w // dungeon.width, self.grid_rect.h // dungeon.height)
        self.origin = (
            self.grid_rect.x + (self.grid_rect.w - dungeon.width * self.cell) // 2,
            self.grid_rect.y + (self.grid_rect.h - dungeon.height * self.cell) // 2,
        )
        self._build_map_surface()
        self.overlays = {}
        for key, color, alpha in (("explored", COL["explored"], 115),
                                  ("explored_key", COL["explored_key"], 115),
                                  ("frontier", COL["frontier"], 175)):
            surf = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
            surf.fill((*color, alpha))
            self.overlays[key] = surf
        self.reset_run()

    def change_level(self, step):
        self.level_index = (self.level_index + step) % len(LEVELS)
        self.is_random = self.is_custom = False
        self.load_dungeon(LEVELS[self.level_index])

    def new_random_level(self):
        seed = random.randint(1, 9999)
        self.is_random, self.is_custom = True, False
        self.load_dungeon(random_dungeon(seed=seed))
        self.message = f"Generated {self.dungeon.name}. It is guaranteed to be solvable."

    # ================================================================
    #  Run state
    # ================================================================
    def reset_run(self):
        self.phase = "idle"          # idle -> exploring -> walking -> finished
        self.result = None
        self.explore_pos = 0.0
        self.walk_pos = 0.0
        self.ai_index = 0
        self.paused = False
        self.banner = None
        self.frontier = {}
        self.expanded_set = set()
        self._fr_pos = 0
        self._fr_seq = 0
        self._h_cache = {}
        self._queue_cache = None
        self.exp_index = {}
        self.run_heuristic = self.heuristic
        # manual play
        self.manual_state = self.dungeon.start_state
        self.manual_cost = 0
        self.manual_steps = 0
        self.manual_trail = [self.dungeon.start_state]
        self.manual_history = []
        self.manual_optimal = None
        self.hint_path = None
        self.hints_used = 0
        if self.editing:
            self.message = ("Map editor: choose a brush, then click or drag on the map. "
                            "Right-click erases to floor.")
        elif self.mode == "manual":
            self.message = ("Manual mode: move with the arrow keys or WASD. Collect the key, then "
                            "reach the treasure chamber. T = hint, Backspace = undo.")
        else:
            extra = ""
            if self.algorithm in INFORMED:
                extra = f" (heuristic: {HEURISTIC_LABELS[HEURISTICS[self.heuristic_index]]})"
            self.message = (f"{FULL_NAMES[self.algorithm]}{extra}. Press Run (Space) to watch it, "
                            "or Step (F) to advance one node at a time.")

    @property
    def heuristic(self):
        return HEURISTICS[self.heuristic_index]

    def run_ai(self):
        if self.editing:
            return
        if self.mode != "ai":
            self.message = "Switch to AI Solver mode (M) to run a search algorithm."
            return
        self.result = run_algorithm(self.algorithm, self.dungeon, self.depth_limit,
                                    heuristic=self.heuristic)
        self.phase = "exploring"
        self.explore_pos = 0.0
        self.walk_pos = 0.0
        self.ai_index = 0
        self.paused = False
        self.banner = None
        self.run_heuristic = self.heuristic
        self.frontier = {self.dungeon.start_state: (0, 0)}
        self.expanded_set = set()
        self._fr_pos = 0
        self._fr_seq = 1
        self._h_cache = {}
        self._queue_cache = None
        self.exp_index = {state: i for i, state in enumerate(self.result.explored)}
        self.message = (f"{FULL_NAMES[self.algorithm]} is exploring... "
                        "(orange = frontier, blue = explored)")

    def step_once(self):
        """Advance exactly one node (exploring) or one cell (walking)."""
        if self.mode != "ai" or self.editing:
            return
        if self.result is None:
            self.run_ai()
            self.paused = True
            self.explore_pos = 1.0
            self._check_exploring_done()
            return
        self.paused = True
        if self.phase == "exploring":
            self.explore_pos = float(int(self.explore_pos) + 1)
            self._check_exploring_done()
        elif self.phase == "walking":
            self.walk_pos = float(int(self.walk_pos) + 1)
            self._advance_walking(0.0)

    def toggle_pause(self):
        if self.mode == "ai" and self.phase in ("exploring", "walking"):
            self.paused = not self.paused

    # ---------------------------------------------------- animation steps
    def _check_exploring_done(self):
        n = len(self.result.explored)
        if self.explore_pos >= n:
            self.explore_pos = float(n)
            self._finish_exploring()

    def _advance_exploring(self, amount):
        before = int(self.explore_pos)
        self.explore_pos += amount
        if int(self.explore_pos) != before:
            now = pygame.time.get_ticks()
            if now - self._last_blip > 70:
                self._last_blip = now
                self.sound.play("blip")
        self._check_exploring_done()

    def _advance_walking(self, amount):
        path = self.result.path
        last = len(path) - 1
        prev = self.ai_index
        self.walk_pos = min(self.walk_pos + amount, float(last))
        self.ai_index = min(int(self.walk_pos), last)
        if self.ai_index != prev:
            self.sound.play("tick")
            if path[self.ai_index][2] and not path[prev][2]:
                self._key_effect()
        if self.walk_pos >= last:
            self._finish_walking()

    def _finish_exploring(self):
        res = self.result
        if res.status == SUCCESS:
            self.phase = "walking"
            self.walk_pos = 0.0
            self.ai_index = 0
            self.message = (f"{FULL_NAMES[res.algorithm]} found a path! "
                            f"Length {res.length}, cost {res.cost:g}, {res.expanded} nodes expanded.")
        else:
            self.phase = "finished"
            self.sound.play("fail")
            if res.status == FAILURE:
                title = "No path found"
                line = "Every reachable state was explored - the treasure cannot be reached."
                self.message = (f"{FULL_NAMES[res.algorithm]} explored every reachable state "
                                "and found no path to the treasure.")
            else:
                title = "Depth limit reached"
                line = f"No solution within depth {res.depth_limit}. Raise the limit and run again."
                self.message = (f"Depth limit {res.depth_limit} reached - no solution within this "
                                "limit. Raise the limit (+ button or = key) and run again.")
            self.banner = {"title": title, "lines": [line], "stars": None, "color": COL["bad"], "t": 0.0}

    def _finish_walking(self):
        res = self.result
        self.phase = "finished"
        self.message = (f"Treasure found by {FULL_NAMES[res.algorithm]}! Length {res.length}, "
                        f"cost {res.cost:g}, {res.expanded} nodes expanded. Press R to reset.")
        self._victory()
        self.banner = {
            "title": f"Treasure found by {res.algorithm}!",
            "lines": [f"{res.length} steps   |   cost {res.cost:g}   |   {res.expanded} nodes expanded   |   "
                      f"peak frontier {res.max_frontier}"],
            "stars": None, "color": COL["good"], "t": 0.0,
        }

    def _victory(self):
        self.sound.play("win")
        center = self.cell_center(*self.dungeon.goal)
        colors = [(255, 214, 64), (255, 120, 120), (120, 220, 255), (150, 255, 160), (220, 150, 255)]
        for _ in range(3):
            self.particles.burst(center, colors, n=34, speed=230, life=1.3, gravity=300, size=4)

    def _key_effect(self):
        self.sound.play("key")
        self.particles.burst(self.cell_center(*self.dungeon.key),
                             [(255, 214, 64), (255, 240, 150), (255, 255, 255)],
                             n=20, speed=120, life=0.7, gravity=120, size=3)

    # ---------------------------------------------------------- settings
    def toggle_mode(self):
        if self.editing:
            return
        self.mode = "manual" if self.mode == "ai" else "ai"
        self.reset_run()

    def select_algorithm(self, name):
        if self.editing:
            return
        self.algorithm = name
        self.mode = "ai"
        self.reset_run()

    def cycle_heuristic(self):
        if self.editing:
            return
        self.heuristic_index = (self.heuristic_index + 1) % len(HEURISTICS)
        self.mode = "ai"
        self.reset_run()
        self.message = (f"Heuristic: {HEURISTIC_LABELS[self.heuristic]}. "
                        + ("It over-estimates (inadmissible): A* may lose optimality."
                           if self.heuristic == "weighted" else
                           "Used by Greedy Best-First and A* only.")
                        + "  Press Run to try it.")

    def change_depth(self, delta):
        self.depth_limit = max(1, min(S.MAX_DEPTH_LIMIT, self.depth_limit + delta))

    def change_speed(self, delta):
        self.speed_index = max(0, min(len(S.SPEED_STEPS) - 1, self.speed_index + delta))

    def toggle_inspector(self):
        self.show_inspector = not self.show_inspector
        self.message = ("Inspector on: hover a cell for g / h / f and its parent; the queue panel shows what "
                        "will be expanded next. Use Step (F) to go node by node." if self.show_inspector
                        else "Inspector off.")

    def open_race(self):
        if self.editing:
            return
        self.race_screen.open(self.dungeon, self.depth_limit, self.heuristic)
        self.state = "race"

    def open_bench(self):
        if self.editing:
            return
        self.bench_screen.open(self.depth_limit, self.heuristic)
        self.state = "bench"

    def toggle_sound(self):
        on = self.sound.toggle()
        self.message = "Sound on." if on else "Sound muted."

    # ================================================================
    #  Manual play
    # ================================================================
    def manual_move(self, dr, dc):
        if self.mode != "manual" or self.phase == "finished" or self.editing:
            return
        d = self.dungeon
        r, c, has_key = self.manual_state
        outcome = d.step(self.manual_state, dr, dc)
        if outcome is None:
            self.sound.play("bump")
            if (r + dr, c + dc) == d.goal and not has_key:
                self.message = "The treasure chamber is locked! Find the key first."
            else:
                self.message = "A wall blocks the way."
            return
        new_state, cost = outcome
        self.manual_history.append((self.manual_state, cost))
        self.manual_state = new_state
        self.manual_cost += cost
        self.manual_steps += 1
        self.manual_trail.append(new_state)
        self.hint_path = None
        self.sound.play("tick")
        if new_state[2] and not has_key:
            self._key_effect()
            self.message = "You picked up the key! Now find the treasure chamber."
        else:
            self.message = f"Moved ({cost} cost)."
        if d.is_goal(new_state):
            self.phase = "finished"
            best = run_algorithm("A*", d, heuristic="manhattan")
            self.manual_optimal = best.cost
            ratio = best.cost / self.manual_cost if self.manual_cost else 1
            stars = 3 if self.manual_cost == best.cost else (2 if ratio >= 0.8 else 1)
            verdict = ("a perfect run!" if stars == 3 else f"the optimal cost was {best.cost:g}.")
            self.message = (f"Treasure found in {self.manual_steps} steps with cost "
                            f"{self.manual_cost} - {verdict} Press R to play again.")
            self._victory()
            self.banner = {"title": "You found the treasure!",
                           "lines": [f"{self.manual_steps} steps   |   cost {self.manual_cost}   |   "
                                     f"optimal {best.cost:g}   |   hints used {self.hints_used}"],
                           "stars": stars, "color": COL["accent"], "t": 0.0}

    def undo_move(self):
        if self.mode != "manual" or self.editing or not self.manual_history:
            return
        prev_state, cost = self.manual_history.pop()
        self.manual_state = prev_state
        self.manual_cost -= cost
        self.manual_steps -= 1
        self.manual_trail.pop()
        self.hint_path = None
        self.phase = "idle"
        self.banner = None
        self.message = "Undid the last move."

    def use_hint(self):
        if self.mode != "manual" or self.editing or self.phase == "finished":
            return
        res = run_algorithm("A*", self.dungeon, heuristic="manhattan", start=self.manual_state)
        if not res.found:
            self.message = "Hint: from here the treasure can no longer be reached."
            return
        self.hint_path = res.path
        self.hints_used += 1
        self.message = (f"Hint: the cheapest way to finish costs {res.cost:g} "
                        f"({res.length} steps) - shown in green.")

    # ================================================================
    #  Map editor
    # ================================================================
    def toggle_editor(self):
        if self.editing:
            self.editing = False
            self.reset_run()
            if self.editor_valid:
                self.message = "Custom map ready. Pick an algorithm and press Run - or press C to compare."
            else:
                self.message = ("Warning: the treasure is unreachable on this map - "
                                "every algorithm will report 'No path found'. Great for testing!")
            return
        if not self.is_custom:
            self.dungeon = self.dungeon.clone("Custom map")
            self.is_custom, self.is_random = True, False
        self.mode = "ai"
        self.editing = True
        self.editor_valid = is_solvable(self.dungeon)
        self.reset_run()

    def cell_at(self, pos):
        x, y = pos[0] - self.origin[0], pos[1] - self.origin[1]
        if x < 0 or y < 0:
            return None
        r, c = y // self.cell, x // self.cell
        if r >= self.dungeon.height or c >= self.dungeon.width:
            return None
        return int(r), int(c)

    def paint_at(self, pos, button):
        cell = self.cell_at(pos)
        if cell is None:
            return
        brush = self.brush if button == 1 else "floor"
        changed, msg = self.dungeon.paint(cell[0], cell[1], brush)
        for r, c in changed:
            self._draw_cell(self.map_surface, r, c)
        if changed:
            self.editor_valid = is_solvable(self.dungeon)
            self.reset_run()
        if msg:
            self.message = msg

    # ================================================================
    #  Dashboard / export
    # ================================================================
    def open_dashboard(self):
        d, limit, hname = self.dungeon, self.depth_limit, self.heuristic
        alg_rows = []
        for name in ALGORITHM_ORDER:
            res = run_algorithm(name, d, limit, heuristic=hname)
            label = name
            if name == "DLS":
                label = f"DLS (limit {limit})"
            elif name in INFORMED:
                label = f"{name} ({HEURISTIC_LABELS[hname]})"
            elif name == "IDS" and res.found:
                label = f"IDS (depth {res.depth_limit})"
            alg_rows.append(Row(label, res, name, hname))
        heur_rows = [Row(f"{name} - {HEURISTIC_LABELS[h]}",
                         run_algorithm(name, d, limit, heuristic=h), name, h)
                     for name in INFORMED for h in HEURISTICS]
        pages = [
            {"title": "Algorithm comparison", "rows": alg_rows,
             "footer": "BFS/IDS minimise steps; UCS and A* minimise cost. A* reaches the same optimal cost "
                       "as UCS while expanding far fewer nodes."},
            {"title": "Heuristic study (Greedy / A*)", "rows": heur_rows,
             "footer": "A better (larger but admissible) heuristic means fewer expansions: Manhattan > "
                       "Euclidean > Chebyshev > Zero. * x3 is inadmissible, so A* is no longer guaranteed "
                       "optimal."},
        ]
        self.dashboard.set_pages(f"Map: {d.name}   |   DLS depth limit: {limit}   |   "
                                 "terrain cost: floor 1, mud 3, water 5", pages)
        self.show_dashboard = True

    def save_csv(self):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        safe = "".join(ch if ch.isalnum() else "_" for ch in self.dungeon.name).strip("_")
        path = os.path.join(RESULTS_DIR, f"comparison_{safe}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["table", "method", "algorithm", "heuristic", "status", "path_length",
                             "path_cost", "nodes_expanded", "peak_frontier", "time_ms", "depth_limit"])
            for title, row in self.dashboard.all_rows():
                r = row.result
                writer.writerow([title, row.label, row.algorithm, row.heuristic, r.status, r.length,
                                 f"{r.cost:g}", r.expanded, r.max_frontier, f"{r.time_ms:.3f}",
                                 r.depth_limit if r.depth_limit is not None else ""])
        self.dashboard.note = f"Saved: results/{os.path.basename(path)}"

    def save_screenshot(self):
        os.makedirs(SHOT_DIR, exist_ok=True)
        path = os.path.join(SHOT_DIR, time.strftime("screenshot_%Y%m%d_%H%M%S.png"))
        pygame.image.save(self.screen, path)
        note = f"Screenshot saved: screenshots/{os.path.basename(path)}"
        if self.show_dashboard:
            self.dashboard.note = note
        else:
            self.message = note

    # ================================================================
    #  Buttons
    # ================================================================
    def _build_buttons(self):
        px, py = self.panel_rect.x, self.panel_rect.y
        self.algo_buttons = {}
        for i, name in enumerate(UNINFORMED):
            self.algo_buttons[name] = Button((px + 16, py + 44 + i * 36, 162, 30), BUTTON_LABELS[name],
                                             lambda n=name: self.select_algorithm(n))
        for i, name in enumerate(INFORMED):
            self.algo_buttons[name] = Button((px + 190, py + 44 + i * 36, 162, 30), BUTTON_LABELS[name],
                                             lambda n=name: self.select_algorithm(n))

        self.heur_button = Button((px + 190, py + 136, 162, 28), "", self.cycle_heuristic)
        self.depth_minus = Button((px + 190, py + 186, 36, 28), "-", lambda: self.change_depth(-5))
        self.depth_plus = Button((px + 316, py + 186, 36, 28), "+", lambda: self.change_depth(5))

        self.speed_minus = Button((px + 16, py + 230, 30, 30), "-", lambda: self.change_speed(-1))
        self.speed_plus = Button((px + 122, py + 230, 30, 30), "+", lambda: self.change_speed(1))
        self.pause_button = Button((px + 160, py + 230, 100, 30), "Pause (P)", self.toggle_pause)
        self.step_button = Button((px + 266, py + 230, 86, 30), "Step (F)", self.step_once)

        self.mode_button = Button((px + 16, py + 268, 336, 30), "", self.toggle_mode)
        self.level_prev = Button((px + 16, py + 304, 36, 30), "<", lambda: self.change_level(-1))
        self.level_next = Button((px + 316, py + 304, 36, 30), ">", lambda: self.change_level(1))
        self.run_button = Button((px + 16, py + 340, 162, 30), "Run  (Space)", self.run_ai)
        self.reset_button = Button((px + 190, py + 340, 162, 30), "Reset  (R)", self.reset_run)
        self.random_button = Button((px + 16, py + 376, 162, 30), "Random Map  (N)", self.new_random_level)
        self.compare_button = Button((px + 190, py + 376, 162, 30), "Compare All  (C)", self.open_dashboard)
        self.edit_button = Button((px + 16, py + 412, 104, 30), "", self.toggle_editor)
        self.hint_button = Button((px + 132, py + 412, 104, 30), "Hint  (T)", self.use_hint)
        self.sound_button = Button((px + 248, py + 412, 104, 30), "", self.toggle_sound)
        self.inspect_button = Button((px + 16, py + 448, 104, 30), "Inspect (I)", self.toggle_inspector)
        self.race_button = Button((px + 132, py + 448, 104, 30), "Race (V)", self.open_race)
        self.bench_button = Button((px + 248, py + 448, 104, 30), "Bench (B)", self.open_bench)

        self.buttons = (list(self.algo_buttons.values()) + [
            self.heur_button, self.depth_minus, self.depth_plus, self.speed_minus, self.speed_plus,
            self.pause_button, self.step_button, self.mode_button, self.level_prev, self.level_next,
            self.run_button, self.reset_button, self.random_button, self.compare_button,
            self.edit_button, self.hint_button, self.sound_button,
            self.inspect_button, self.race_button, self.bench_button])

        # --- editor palette (replaces the stats box while editing)
        self.editor_buttons = []
        for i, (label, brush) in enumerate(BRUSHES):
            x = px + 22 + (i % 4) * 81
            y = py + BOX_Y + 28 + (i // 4) * 33
            b = Button((x, y, 75, 28), label, lambda br=brush: self._set_brush(br))
            b.brush = brush
            self.editor_buttons.append(b)
        done = Button((px + 22 + 3 * 81, py + BOX_Y + 28 + 33, 75, 28), "Done", self.toggle_editor)
        done.brush = None
        self.editor_buttons.append(done)

    def _set_brush(self, brush):
        self.brush = brush

    def _active_buttons(self):
        return self.buttons + (self.editor_buttons if self.editing else [])

    def _refresh_buttons(self):
        ai = self.mode == "ai" and not self.editing
        for name, b in self.algo_buttons.items():
            b.selected = ai and name == self.algorithm
            b.enabled = not self.editing
        self.heur_button.label = f"H: {HEURISTIC_LABELS[self.heuristic]}"
        self.heur_button.selected = ai and self.algorithm in INFORMED
        self.heur_button.enabled = not self.editing
        self.depth_minus.enabled = self.depth_plus.enabled = ai
        self.run_button.enabled = ai
        self.step_button.enabled = ai
        self.pause_button.enabled = ai and self.phase in ("exploring", "walking")
        self.pause_button.label = "Resume (P)" if self.paused else "Pause (P)"
        self.pause_button.selected = self.paused and self.pause_button.enabled
        self.mode_button.enabled = not self.editing
        self.mode_button.label = ("Mode: AI Solver  (M to switch)" if self.mode == "ai"
                                  else "Mode: Manual Play  (M to switch)")
        self.mode_button.selected = self.mode == "manual"
        self.hint_button.enabled = (self.mode == "manual" and not self.editing and self.phase != "finished")
        self.edit_button.label = "Done  (E)" if self.editing else "Edit Map (E)"
        self.edit_button.selected = self.editing
        self.inspect_button.selected = self.show_inspector
        self.sound_button.label = "Sound: On" if self.sound.enabled else "Sound: Off"
        if not self.sound.ok:
            self.sound_button.label = "No audio"
            self.sound_button.enabled = False
        for b in self.editor_buttons:
            b.selected = b.brush == self.brush

    # ================================================================
    #  Events
    # ================================================================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
                self.save_screenshot()
                continue
            if self.state == "title":
                self._title_event(event)
            elif self.state == "race":
                if self.race_screen.handle_event(event) == "back":
                    self.state = "play"
            elif self.state == "bench":
                if self.bench_screen.handle_event(event) == "back":
                    self.state = "play"
            elif self.show_help:
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self.show_help = False
            elif self.show_dashboard:
                self._dashboard_event(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                consumed = False
                for b in self._active_buttons():
                    if b.handle(event):
                        consumed = True
                        self.sound.play("click")
                        break
                if not consumed and self.editing and event.button in (1, 3):
                    self.paint_at(event.pos, event.button)
            elif event.type == pygame.MOUSEMOTION and self.editing:
                if event.buttons[0]:
                    self.paint_at(event.pos, 1)
                elif event.buttons[2]:
                    self.paint_at(event.pos, 3)
            elif event.type == pygame.KEYDOWN:
                self._key_event(event.key)
                if event.key in MOVE_KEYS:
                    self.move_cooldown = 0.22

    def _title_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            else:
                self.state = "play"
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.state = "play"

    def _dashboard_event(self, event):
        dash = self.dashboard
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_c):
                self.show_dashboard = False
            elif event.key == pygame.K_s:
                self.save_csv()
            elif event.key == pygame.K_TAB:
                dash.next_metric()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                dash.next_page()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if dash.close_button.rect.collidepoint(event.pos):
                self.show_dashboard = False
            elif dash.metric_button.rect.collidepoint(event.pos):
                dash.next_metric()
            else:
                tab = dash.tab_at(event.pos)
                if tab is not None:
                    dash.page = tab
                    return
                row = dash.row_at(event.pos)
                if row is not None:
                    self.show_dashboard = False
                    self.heuristic_index = HEURISTICS.index(row.heuristic)
                    self.select_algorithm(row.algorithm)

    def _key_event(self, key):
        if key == pygame.K_ESCAPE:
            if self.editing:
                self.toggle_editor()
            else:
                self.running = False
        elif key == pygame.K_F1:
            self.show_help = True
        elif self.editing and pygame.K_1 <= key <= pygame.K_7:
            self.brush = BRUSHES[key - pygame.K_1][1]
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self.run_ai()
        elif key == pygame.K_f:
            self.step_once()
        elif key == pygame.K_p:
            self.toggle_pause()
        elif key == pygame.K_r:
            self.reset_run()
        elif key == pygame.K_m:
            self.toggle_mode()
        elif key == pygame.K_n:
            self.new_random_level()
        elif key == pygame.K_c:
            self.open_dashboard()
        elif key == pygame.K_e:
            self.toggle_editor()
        elif key == pygame.K_i:
            self.toggle_inspector()
        elif key == pygame.K_v:
            self.open_race()
        elif key == pygame.K_b:
            self.open_bench()
        elif key == pygame.K_t:
            self.use_hint()
        elif key == pygame.K_h:
            self.cycle_heuristic()
        elif key == pygame.K_x:
            self.toggle_sound()
        elif key in (pygame.K_BACKSPACE, pygame.K_z):
            self.undo_move()
        elif key == pygame.K_LEFTBRACKET:
            self.change_level(-1)
        elif key == pygame.K_RIGHTBRACKET:
            self.change_level(1)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.change_depth(5)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_depth(-5)
        elif key == pygame.K_PERIOD:
            self.change_speed(1)
        elif key == pygame.K_COMMA:
            self.change_speed(-1)
        elif pygame.K_1 <= key <= pygame.K_7:
            self.select_algorithm(ALGORITHM_ORDER[key - pygame.K_1])
        elif key in MOVE_KEYS:
            self.manual_move(*MOVE_KEYS[key])

    # ================================================================
    #  Update
    # ================================================================
    def update(self, dt):
        dt = min(dt, 0.05)
        self.time += dt
        self.particles.update(dt)
        if self.banner:
            self.banner["t"] += dt
        if self.state == "race":
            self.race_screen.update(dt)
            return
        if self.state == "bench":
            self.bench_screen.update(dt)
            return
        if self.state != "play":
            return
        if self.mode == "manual":
            self.move_cooldown -= dt
            if (self.move_cooldown <= 0 and not self.show_dashboard
                    and not self.show_help and not self.editing):
                pressed = pygame.key.get_pressed()
                for key, (dr, dc) in MOVE_KEYS.items():
                    if pressed[key]:
                        self.manual_move(dr, dc)
                        self.move_cooldown = 0.09
                        break
            return
        if self.result is None or self.paused or self.editing:
            return
        mult = S.SPEED_STEPS[self.speed_index]
        if self.phase == "exploring":
            self._advance_exploring(S.EXPLORE_NODES_PER_SEC * mult * dt)
        elif self.phase == "walking":
            self._advance_walking(min(S.WALK_STEPS_PER_SEC * mult, 40) * dt)

    # ================================================================
    #  Drawing helpers
    # ================================================================
    def cell_rect(self, r, c):
        return pygame.Rect(self.origin[0] + c * self.cell, self.origin[1] + r * self.cell,
                           self.cell, self.cell)

    def cell_center(self, r, c):
        return self.cell_rect(r, c).center

    def _build_map_surface(self):
        self.map_surface = self.render_map(self.dungeon, self.cell)

    def render_map(self, dungeon, cs):
        """Pre-render a whole dungeon at the given cell size (also used by the race screen)."""
        surf = pygame.Surface((dungeon.width * cs, dungeon.height * cs))
        for r in range(dungeon.height):
            for c in range(dungeon.width):
                self._draw_cell(surf, r, c, cs, dungeon)
        return surf

    def _draw_cell(self, surf, r, c, cs=None, dungeon=None):
        d = dungeon or self.dungeon
        cs = cs or self.cell
        rect = pygame.Rect(c * cs, r * cs, cs, cs)
        t = d.terrain[r][c]
        tiny = self.fonts["tiny"]
        if t == S.WALL:
            pygame.draw.rect(surf, COL["wall"], rect)
            pygame.draw.line(surf, COL["wall_line"], (rect.x, rect.y + cs // 2), (rect.right, rect.y + cs // 2))
            pygame.draw.line(surf, COL["wall_line"], (rect.x + cs // 4, rect.y), (rect.x + cs // 4, rect.y + cs // 2))
            pygame.draw.line(surf, COL["wall_line"], (rect.x + 3 * cs // 4, rect.y + cs // 2),
                             (rect.x + 3 * cs // 4, rect.bottom))
            pygame.draw.rect(surf, COL["wall_line"], rect, 1)
            pygame.draw.line(surf, (66, 58, 86), (rect.x + 1, rect.y + 1), (rect.right - 2, rect.y + 1))
        elif t == S.MUD:
            pygame.draw.rect(surf, COL["mud"], rect)
            for fx, fy in ((0.22, 0.28), (0.66, 0.46), (0.34, 0.74), (0.78, 0.80)):
                pygame.draw.circle(surf, COL["mud_dot"], (rect.x + int(fx * cs), rect.y + int(fy * cs)),
                                   max(2, cs // 11))
            if cs >= 20:
                draw_text(surf, "3", tiny, (225, 190, 140), rect.center, "center")
        elif t == S.WATER:
            pygame.draw.rect(surf, COL["water"], rect)
            for fy in (0.30, 0.70):
                y = rect.y + int(fy * cs)
                pts = [(rect.x + int(i * cs / 4), y + (3 if i % 2 else -3)) for i in range(5)]
                pygame.draw.lines(surf, COL["water_line"], False, pts, 1)
            if cs >= 20:
                draw_text(surf, "5", tiny, (220, 240, 255), rect.center, "center")
        else:
            color = COL["floor_a"] if (r + c) % 2 == 0 else COL["floor_b"]
            pygame.draw.rect(surf, color, rect)
            sx = rect.x + (r * 13 + c * 7) % max(1, cs - 4) + 2
            sy = rect.y + (r * 5 + c * 11) % max(1, cs - 4) + 2
            pygame.draw.circle(surf, (92, 86, 108), (sx, sy), 1)

    def explorer_pixel(self, state):
        if (self.mode == "ai" and self.phase == "walking" and self.result is not None
                and self.result.found):
            path, i = self.result.path, self.ai_index
            j = min(i + 1, len(path) - 1)
            a, b = self.cell_center(path[i][0], path[i][1]), self.cell_center(path[j][0], path[j][1])
            f = max(0.0, min(1.0, self.walk_pos - i))
            return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f))
        return self.cell_center(state[0], state[1])

    # ================================================================
    #  Drawing
    # ================================================================
    def current_state(self):
        if self.mode == "manual":
            return self.manual_state
        if self.result is not None and self.result.found and self.phase in ("walking", "finished"):
            return self.result.path[self.ai_index]
        return self.dungeon.start_state

    def _sync_frontier(self, shown):
        res = self.result
        while self._fr_pos < shown:
            i = self._fr_pos
            state = res.explored[i]
            self.frontier.pop(state, None)
            self.expanded_set.add(state)
            for kid, g in zip(res.generated[i], res.child_g[i]):
                if kid not in self.expanded_set:
                    self.frontier.pop(kid, None)          # a re-pushed state moves to the newest slot
                    self.frontier[kid] = (self._fr_seq, g)
                    self._fr_seq += 1
            self._fr_pos += 1

    def draw_grid(self):
        d = self.dungeon
        pygame.draw.rect(self.screen, COL["panel"], self.grid_rect.inflate(8, 8), border_radius=8)
        self.screen.blit(self.map_surface, self.origin)

        # --- frontier + explored states (AI mode)
        if self.mode == "ai" and self.result is not None and not self.editing:
            res = self.result
            shown = int(self.explore_pos) if self.phase == "exploring" else len(res.explored)
            if self.phase == "exploring":
                self._sync_frontier(shown)
                for r, c, _k in self.frontier:
                    self.screen.blit(self.overlays["frontier"], self.cell_rect(r, c).topleft)
            for r, c, has_key in res.explored[:shown]:
                self.screen.blit(self.overlays["explored_key" if has_key else "explored"],
                                 self.cell_rect(r, c).topleft)
            if self.phase == "exploring" and shown > 0:
                r, c, _k = res.explored[shown - 1]
                pygame.draw.rect(self.screen, (255, 255, 255), self.cell_rect(r, c), 2)

        # --- editor grid lines
        if self.editing:
            for r in range(d.height + 1):
                y = self.origin[1] + r * self.cell
                pygame.draw.line(self.screen, (96, 90, 118), (self.origin[0], y),
                                 (self.origin[0] + d.width * self.cell, y))
            for c in range(d.width + 1):
                x = self.origin[0] + c * self.cell
                pygame.draw.line(self.screen, (96, 90, 118), (x, self.origin[1]),
                                 (x, self.origin[1] + d.height * self.cell))
            hover = self.cell_at(pygame.mouse.get_pos())
            if hover is not None:
                pygame.draw.rect(self.screen, COL["accent"], self.cell_rect(*hover), 2)

        # --- start marker
        pygame.draw.circle(self.screen, COL["start"], self.cell_center(*d.start), int(self.cell * 0.42), 2)

        state = self.current_state()
        has_key = state[2]
        pos = self.explorer_pixel(state)

        # --- path / trail / hint
        if (self.mode == "ai" and self.result is not None and self.result.found
                and self.phase in ("walking", "finished")):
            pts = [self.cell_center(r, c) for r, c, _k in self.result.path[:self.ai_index + 1]]
            if self.phase == "walking":
                pts.append(pos)
            if len(pts) >= 2:
                pygame.draw.lines(self.screen, COL["path"], False, pts, 4)
        elif self.mode == "manual":
            if len(self.manual_trail) >= 2:
                pts = [self.cell_center(r, c) for r, c, _k in self.manual_trail]
                pygame.draw.lines(self.screen, (150, 230, 220), False, pts, 2)
            if self.hint_path:
                pts = [self.cell_center(r, c) for r, c, _k in self.hint_path]
                if len(pts) >= 2:
                    pygame.draw.lines(self.screen, COL["hint"], False, pts, 3)
                for p in pts[1:]:
                    pygame.draw.circle(self.screen, COL["hint"], p, 3)

        # --- key, chest, explorer
        if not has_key:
            draw_key(self.screen, self.cell_center(*d.key), self.cell, self.time)
        draw_chest(self.screen, self.cell_rect(*d.goal), has_key, self.time)
        moving = (self.mode == "ai" and self.phase == "walking" and not self.paused)
        draw_explorer(self.screen, pos, self.cell, has_key, self.time, moving)

    # ------------------------------------------------------- inspector
    def _h(self, state):
        if state not in self._h_cache:
            self._h_cache[state] = self.dungeon.heuristic_as(state, self.run_heuristic)
        return self._h_cache[state]

    def queue_snapshot(self):
        """Frontier entries sorted in the order the algorithm will expand them."""
        if self._queue_cache is not None and self._queue_cache[0] == self._fr_pos:
            return self._queue_cache[1]
        alg = self.result.algorithm
        items = [(state, g, self._h(state), seq) for state, (seq, g) in self.frontier.items()]
        if alg == "BFS":
            key = lambda it: it[3]
        elif alg in ("DFS", "DLS", "IDS"):
            key = lambda it: -it[3]
        elif alg == "UCS":
            key = lambda it: (it[1], it[3])
        elif alg == "Greedy":
            key = lambda it: (it[2], it[3])
        else:                                   # A*
            key = lambda it: (it[1] + it[2], it[2], it[3])
        items.sort(key=key)
        self._queue_cache = (self._fr_pos, items)
        return items

    def cell_info_lines(self, r, c):
        d = self.dungeon
        lines = [f"Cell ({r}, {c}):  {TERRAIN_NAMES[d.terrain[r][c]]}"]
        marker = d.marker_at(r, c)
        if marker:
            lines[0] += {"start": "  [START]", "key": "  [KEY]", "goal": "  [TREASURE]"}[marker]
        res = self.result
        if res is None or self.mode != "ai" or d.terrain[r][c] == S.WALL:
            return lines
        shown = int(self.explore_pos) if self.phase == "exploring" else len(res.explored)
        for has_key in (False, True):
            state = (r, c, has_key)
            tag = "with key" if has_key else "no key"
            idx = self.exp_index.get(state)
            if idx is not None and idx < shown:
                g, h = res.exp_g[idx], self._h(state)
                parent = res.exp_parent[idx]
                par = "none (start)" if parent is None else f"({parent[0]}, {parent[1]})"
                lines.append(f"{tag}: expanded #{idx + 1}")
                lines.append(f"   g={num(g)}  h={num(h)}  f={num(g + h)}   parent {par}")
            elif state in self.frontier and self.phase == "exploring":
                _seq, g = self.frontier[state]
                h = self._h(state)
                lines.append(f"{tag}: waiting in the frontier")
                lines.append(f"   g={num(g)}  h={num(h)}  f={num(g + h)}")
        return lines

    def draw_inspector(self):
        small, tiny = self.fonts["small"], self.fonts["tiny"]
        res = self.result
        # --- queue panel (top-right corner of the map)
        w, rows = 300, 7
        panel = pygame.Rect(self.grid_rect.right - w - 6, self.grid_rect.y + 6, w, 62 + 17 * (rows + 2))
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (16, 13, 26, 232), (0, 0, panel.w, panel.h), border_radius=10)
        pygame.draw.rect(bg, COL["panel_edge"], (0, 0, panel.w, panel.h), 1, border_radius=10)
        self.screen.blit(bg, panel.topleft)
        x, y = panel.x + 12, panel.y + 8
        if res is None or self.mode != "ai":
            draw_text(self.screen, "QUEUE PANEL", small, COL["accent"], (x, y))
            msg = ("Select an algorithm and press Step (F) or Run to watch its queue." if self.mode == "ai"
                   else "Switch to AI Solver mode to see a search queue.")
            for i, line in enumerate(wrap_text(msg, small, w - 24)):
                draw_text(self.screen, line, small, COL["muted"], (x, y + 26 + i * 18))
        else:
            kind, rule = QUEUE_RULE[res.algorithm]
            draw_text(self.screen, f"{kind.upper()}", small, COL["accent"], (x, y))
            draw_text(self.screen, f"next = {rule}", tiny, COL["muted"], (x, y + 19))
            shown = int(self.explore_pos) if self.phase == "exploring" else len(res.explored)
            if self.phase != "exploring":
                self._sync_frontier(len(res.explored))
            if shown > 0:
                i = min(shown, len(res.explored)) - 1
                r, c, k = res.explored[i]
                g, h = res.exp_g[i], self._h(res.explored[i])
                draw_text(self.screen, f"Just expanded: ({r}, {c}){' +key' if k else ''}", small,
                          COL["text"], (x, y + 38))
                draw_text(self.screen, f"g={num(g)}  h={num(h)}  f={num(g + h)}", tiny, COL["muted"], (x, y + 57))
            ty = y + 76
            draw_text(self.screen, "cell", tiny, COL["info"], (x, ty))
            for label, off in (("g", 118), ("h", 172), ("f", 226)):
                draw_text(self.screen, label, tiny, COL["info"], (x + off, ty))
            items = self.queue_snapshot()
            for n, (state, g, h, _seq) in enumerate(items[:rows]):
                ry = ty + 15 + n * 17
                color = COL["frontier"] if n == 0 else COL["text"]
                draw_text(self.screen, f"{n + 1}. ({state[0]},{state[1]}){'+K' if state[2] else ''}",
                          tiny, color, (x, ry))
                draw_text(self.screen, num(g), tiny, color, (x + 118, ry))
                draw_text(self.screen, num(h), tiny, color, (x + 172, ry))
                draw_text(self.screen, num(g + h), tiny, color, (x + 226, ry))
            more = len(items) - rows
            draw_text(self.screen, f"{len(items)} waiting" + (f"  (+{more} more)" if more > 0 else ""),
                      tiny, COL["muted"], (x, ty + 15 + rows * 17 + 2))

        # --- hover tooltip
        cell = self.cell_at(pygame.mouse.get_pos()) if not self.editing else None
        if cell is None:
            return
        pygame.draw.rect(self.screen, (255, 255, 255), self.cell_rect(*cell), 2)
        lines = self.cell_info_lines(*cell)
        width = max(self.fonts["small"].size(line)[0] for line in lines) + 20
        height = 12 + 18 * len(lines)
        mx, my = pygame.mouse.get_pos()
        box = pygame.Rect(mx + 16, my + 16, width, height)
        box.right = min(box.right, self.grid_rect.right - 4)
        box.bottom = min(box.bottom, self.grid_rect.bottom - 4)
        bg = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (16, 13, 26, 240), (0, 0, box.w, box.h), border_radius=8)
        pygame.draw.rect(bg, COL["accent"], (0, 0, box.w, box.h), 1, border_radius=8)
        self.screen.blit(bg, box.topleft)
        for i, line in enumerate(lines):
            draw_text(self.screen, line, self.fonts["small"], COL["text"] if i == 0 else COL["info"],
                      (box.x + 10, box.y + 6 + i * 18))

    def draw_banner(self):
        b = self.banner
        if not b:
            return
        t = b["t"]
        alpha = 255 if t < 5.0 else max(0, int(255 * (1 - (t - 5.0) / 1.5)))
        if alpha <= 0:
            return
        w, h = 600, 82 + (30 if b["stars"] else 0)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (20, 16, 30, 235), (0, 0, w, h), border_radius=12)
        pygame.draw.rect(surf, b["color"], (0, 0, w, h), 2, border_radius=12)
        draw_text(surf, b["title"], self.fonts["big"], b["color"], (w // 2, 10), "midtop")
        y = 46
        for line in b["lines"]:
            draw_text(surf, line, self.fonts["small"], COL["text"], (w // 2, y), "midtop")
            y += 20
        if b["stars"]:
            for i in range(3):
                draw_star(surf, (w // 2 - 40 + i * 40, h - 22), 12,
                          COL["accent"] if i < b["stars"] else (70, 64, 90))
        surf.set_alpha(alpha)
        y_pos = self.grid_rect.bottom - h - 14 if self.show_inspector else self.grid_rect.y + 14
        self.screen.blit(surf, (self.grid_rect.centerx - w // 2, y_pos))

    def draw_status(self):
        pygame.draw.rect(self.screen, COL["panel"], self.status_rect, border_radius=8)
        pygame.draw.rect(self.screen, COL["panel_edge"], self.status_rect, 1, border_radius=8)
        lines = wrap_text(self.message, self.fonts["normal"], self.status_rect.w - 28)[:2]
        y = self.status_rect.y + 8
        for line in lines:
            draw_text(self.screen, line, self.fonts["normal"], COL["text"], (self.status_rect.x + 14, y))
            y += 21

    def draw_chart(self):
        R = self.chart_rect
        small, tiny = self.fonts["small"], self.fonts["tiny"]
        pygame.draw.rect(self.screen, COL["panel"], R, border_radius=8)
        pygame.draw.rect(self.screen, COL["panel_edge"], R, 1, border_radius=8)
        inner = pygame.Rect(R.x + 14, R.y + 26, R.w - 28, R.h - 36)
        pygame.draw.line(self.screen, COL["panel_edge"], (inner.x, inner.bottom), (inner.right, inner.bottom))

        if self.mode == "manual":
            draw_text(self.screen, "Cumulative path cost per move", small, COL["info"], (R.x + 14, R.y + 5))
            costs, total = [0], 0
            for _s, cost in self.manual_history:
                total += cost
                costs.append(total)
            draw_text(self.screen, f"steps {self.manual_steps}   cost {self.manual_cost}", tiny,
                      COL["muted"], (R.right - 14, R.y + 8), "topright")
            if len(costs) >= 2:
                peak = max(costs[-1], 1)
                n = max(len(costs) - 1, 1)
                pts = [(inner.x + inner.w * i / max(n, 20), inner.bottom - inner.h * v / peak)
                       for i, v in enumerate(costs)]
                pygame.draw.lines(self.screen, COL["good"], False, pts, 2)
            return

        draw_text(self.screen, "Frontier size while searching (memory use)", small, COL["info"], (R.x + 14, R.y + 5))
        res = self.result
        if self.editing:
            draw_text(self.screen, "Map editor active - press Done (E) to run algorithms.", small,
                      COL["muted"], inner.center, "center")
        elif res is None or not res.frontier_sizes:
            msg = "Run a search to see how large its frontier grows." if res is None else "No data."
            draw_text(self.screen, msg, small, COL["muted"], inner.center, "center")
        else:
            sizes, n = res.frontier_sizes, len(res.frontier_sizes)
            peak = max(max(sizes), 1)
            shown = max(1, int(self.explore_pos)) if self.phase == "exploring" else n
            shown = min(shown, n)
            step = max(1, n // 300)

            def points(upto):
                idx = list(range(0, upto, step))
                if idx[-1] != upto - 1:
                    idx.append(upto - 1)
                return [(inner.x + inner.w * i / max(n - 1, 1), inner.bottom - inner.h * sizes[i] / peak)
                        for i in idx]

            if n >= 2:
                pygame.draw.lines(self.screen, (64, 58, 90), False, points(n), 1)
                if shown >= 2:
                    pygame.draw.lines(self.screen, COL["frontier"], False, points(shown), 2)
            end = points(shown)[-1]
            pygame.draw.circle(self.screen, COL["frontier"], (int(end[0]), int(end[1])), 4)
            draw_text(self.screen, f"now {sizes[shown - 1]}   peak {peak}   expanded {shown}/{n}", tiny,
                      COL["muted"], (R.right - 14, R.y + 8), "topright")

    def draw_panel(self):
        P = self.panel_rect
        px, py = P.x, P.y
        small, normal = self.fonts["small"], self.fonts["normal"]
        pygame.draw.rect(self.screen, COL["panel"], P, border_radius=10)
        pygame.draw.rect(self.screen, COL["panel_edge"], P, 1, border_radius=10)
        self._refresh_buttons()

        draw_text(self.screen, "UNINFORMED", small, COL["info"], (px + 18, py + 16))
        draw_text(self.screen, "INFORMED", small, COL["info"], (px + 192, py + 16))
        draw_text(self.screen, "Heuristic (Greedy / A*)", small, COL["muted"], (px + 192, py + 116))
        draw_text(self.screen, "Depth limit (DLS)", small, COL["muted"], (px + 192, py + 166))
        ai = self.mode == "ai" and not self.editing
        draw_text(self.screen, self.depth_limit, normal, COL["text"] if ai else COL["muted"],
                  (px + 271, py + 200), "center")
        draw_text(self.screen, f"Speed x{S.SPEED_STEPS[self.speed_index]:g}", small, COL["text"],
                  (px + 84, py + 245), "center")

        if self.is_custom:
            label = "Custom map (edited)"
        elif self.is_random:
            label = self.dungeon.name
        else:
            label = f"Level {self.level_index + 1}/{len(LEVELS)}: {LEVELS[self.level_index].name}"
        draw_text(self.screen, label, small, COL["text"], (px + 184, py + 319), "center")

        for b in self._active_buttons():
            b.draw(self.screen, small)

        if self.editing:
            self._draw_editor_box(px, py)
        else:
            self._draw_stats(px, py)
        self._draw_legend(px, py)

    def _draw_editor_box(self, px, py):
        small, normal = self.fonts["small"], self.fonts["normal"]
        box = pygame.Rect(px + 16, py + BOX_Y, 336, BOX_H)
        pygame.draw.rect(self.screen, COL["bg"], box, border_radius=8)
        pygame.draw.rect(self.screen, COL["panel_edge"], box, 1, border_radius=8)
        draw_text(self.screen, "MAP EDITOR", normal, COL["accent"], (box.x + 12, box.y + 4))
        status = ("Treasure reachable - map is solvable" if self.editor_valid
                  else "Treasure UNREACHABLE (algorithms will fail)")
        draw_text(self.screen, status, self.fonts["tiny"], COL["good"] if self.editor_valid else COL["bad"],
                  (box.x + 12, box.y + 94))
        draw_text(self.screen, "Left-drag paints  |  Right-click erases  |  1-7 pick brush",
                  self.fonts["tiny"], COL["muted"], (box.x + 12, box.y + 106))

    def _draw_stats(self, px, py):
        small, normal = self.fonts["small"], self.fonts["normal"]
        box = pygame.Rect(px + 16, py + BOX_Y, 336, BOX_H)
        pygame.draw.rect(self.screen, COL["bg"], box, border_radius=8)
        pygame.draw.rect(self.screen, COL["panel_edge"], box, 1, border_radius=8)
        x, y = box.x + 12, box.y + 5
        rows = []   # (text, color, font)

        if self.mode == "manual":
            rows.append(("MANUAL PLAY", COL["accent"], normal))
            rows.append((f"Steps: {self.manual_steps}      Cost: {self.manual_cost}", COL["text"], small))
            rows.append((f"Key: {'collected' if self.manual_state[2] else 'not yet'}      "
                         f"Hints used: {self.hints_used}", COL["text"], small))
            if self.manual_optimal is not None:
                rows.append((f"Optimal cost (A*): {self.manual_optimal:g}", COL["good"], small))
            else:
                rows.append(("Goal: get the key, then the treasure.", COL["muted"], small))
                rows.append(("Cheapest route avoids mud and water!", COL["muted"], small))
        else:
            rows.append((FULL_NAMES[self.algorithm].upper(), COL["accent"], normal))
            res = self.result
            if res is None:
                summary, complete, optimal, tcx, scx = INFO[self.algorithm]
                for line in wrap_text(summary, small, box.w - 24)[:2]:
                    rows.append((line, COL["text"], small))
                rows.append((f"Complete: {complete}   Optimal: {optimal}", COL["muted"], small))
                rows.append((f"Time {tcx}   Space {scx}", COL["muted"], small))
                if self.algorithm == "DLS":
                    rows.append((f"Current depth limit: {self.depth_limit}", COL["info"], small))
                elif self.algorithm in INFORMED:
                    rows.append((f"Heuristic: {HEURISTIC_LABELS[self.heuristic]}", COL["info"], small))
            elif self.phase == "exploring":
                rows.append(("Searching...", COL["info"], small))
                rows.append((f"Nodes expanded: {int(self.explore_pos)} / {len(res.explored)}", COL["text"], small))
                cur = res.frontier_sizes[max(0, min(int(self.explore_pos), len(res.frontier_sizes)) - 1)] \
                    if res.frontier_sizes else 0
                rows.append((f"Frontier size now: {cur}", COL["frontier"], small))
                if self.paused:
                    rows.append(("PAUSED - press F to step, P to resume", COL["accent"], small))
            else:
                status = {"success": ("Success", COL["good"]),
                          "failure": ("No path found", COL["bad"]),
                          "depth_limit": ("Depth limit reached", COL["bad"])}[res.status]
                rows.append((f"Status: {status[0]}", status[1], small))
                if res.found:
                    rows.append((f"Length: {res.length} steps     Cost: {res.cost:g}", COL["text"], small))
                rows.append((f"Expanded: {res.expanded}     Peak frontier: {res.max_frontier}", COL["text"], small))
                rows.append((f"Time: {res.time_ms:.2f} ms", COL["text"], small))
                if res.algorithm == "DLS":
                    rows.append((f"Depth limit used: {res.depth_limit}", COL["muted"], small))
                elif res.algorithm == "IDS" and res.found:
                    rows.append((f"Solution depth: {res.depth_limit}", COL["muted"], small))
                elif res.algorithm in INFORMED:
                    rows.append((f"Heuristic: {HEURISTIC_LABELS[self.heuristic]}", COL["muted"], small))

        for i, (text, color, font) in enumerate(rows[:6]):
            draw_text(self.screen, text, font, color, (x, y))
            y += 23 if i == 0 else 17

    def _draw_legend(self, px, py):
        tiny = self.fonts["tiny"]
        items = [
            (COL["floor_a"], "Floor (cost 1)"), (COL["explored"], "Explored"),
            (COL["mud"], "Mud (cost 3)"), (COL["explored_key"], "Explored + key"),
            (COL["water"], "Water (cost 5)"), (COL["frontier"], "Frontier (waiting)"),
            (COL["wall"], "Wall"), (COL["path"], "Final path"),
            (COL["key"], "Key"), (COL["chest"], "Treasure"),
        ]
        for i, (color, label) in enumerate(items):
            col, row = i % 2, i // 2
            x = px + 20 + col * 168
            y = py + 614 + row * 14
            pygame.draw.rect(self.screen, color, (x, y + 1, 11, 11), border_radius=2)
            pygame.draw.rect(self.screen, COL["panel_edge"], (x, y + 1, 11, 11), 1, border_radius=2)
            draw_text(self.screen, label, tiny, COL["muted"], (x + 17, y - 1))

    # ---------------------------------------------------------- screens
    def draw_title(self):
        W, H = S.WINDOW_W, S.WINDOW_H
        for y in range(0, H, 6):
            t = y / H
            pygame.draw.rect(self.screen, (int(16 + 26 * t), int(13 + 14 * t), int(30 + 40 * t)), (0, y, W, 6))

        # --- decorative corridor with the explorer running to the chest
        cs = 56
        strip_y = H - 150
        for i in range(W // cs + 2):
            for j in range(2):
                color = COL["floor_a"] if (i + j) % 2 == 0 else COL["floor_b"]
                pygame.draw.rect(self.screen, color, (i * cs, strip_y + j * cs, cs, cs))
        for i in range(W // cs + 2):
            pygame.draw.rect(self.screen, COL["wall"], (i * cs, strip_y - cs, cs, cs))
            pygame.draw.line(self.screen, COL["wall_line"], (i * cs, strip_y - cs // 2), (i * cs + cs, strip_y - cs // 2))
            pygame.draw.rect(self.screen, COL["wall_line"], (i * cs, strip_y - cs, cs, cs), 1)
        cycle = 10.0
        p = (self.time % cycle) / cycle
        ex = -40 + (W + 80) * p
        key_x, chest_x = int(W * 0.45), W - 110
        row_y = strip_y + cs // 2
        got_key = ex > key_x
        if not got_key:
            draw_key(self.screen, (key_x, row_y), cs, self.time)
        draw_chest(self.screen, pygame.Rect(chest_x - cs // 2, strip_y, cs, cs), got_key, self.time)
        draw_explorer(self.screen, (int(ex), row_y), cs, got_key, self.time, True)

        # --- text
        draw_text(self.screen, "AI DUNGEON EXPLORER", self.fonts["title"], COL["accent"], (W // 2, 70), "midtop")
        draw_text(self.screen, "The Lost Temple", self.fonts["sub"], COL["text"], (W // 2, 142), "midtop")
        draw_text(self.screen, "Watch classic AI search algorithms hunt for the key and the treasure.",
                  self.fonts["normal"], COL["muted"], (W // 2, 188), "midtop")

        box = pygame.Rect(W // 2 - 320, 232, 640, 200)
        pygame.draw.rect(self.screen, (30, 27, 44), box, border_radius=12)
        pygame.draw.rect(self.screen, COL["panel_edge"], box, 2, border_radius=12)
        draw_text(self.screen, S.COURSE, self.fonts["big"], COL["info"], (box.centerx, box.y + 14), "midtop")
        draw_text(self.screen, S.DEPARTMENT, self.fonts["small"], COL["muted"], (box.centerx, box.y + 46), "midtop")
        draw_text(self.screen, S.GROUP, self.fonts["normal"], COL["accent"], (box.centerx, box.y + 72), "midtop")
        for i, (name, sid) in enumerate(S.TEAM):
            y = box.y + 108 + i * 28
            draw_text(self.screen, name, self.fonts["normal"], COL["text"], (box.x + 150, y), "topright")
            draw_text(self.screen, sid, self.fonts["normal"], COL["muted"], (box.x + 190, y))

        pulse = 0.5 + 0.5 * math.sin(self.time * 3)
        shade = int(150 + 105 * pulse)
        draw_text(self.screen, "Press any key or click to start", self.fonts["sub"], (shade, shade, int(shade * 0.7)),
                  (W // 2, 470), "midtop")
        draw_text(self.screen, "F1 = help during the game      F12 = screenshot      Esc = quit",
                  self.fonts["small"], COL["muted"], (W // 2, 516), "midtop")

    def draw_help(self):
        dim = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        dim.fill((8, 6, 14, 225))
        self.screen.blit(dim, (0, 0))
        R = pygame.Rect(S.WINDOW_W // 2 - 400, 40, 800, S.WINDOW_H - 80)
        pygame.draw.rect(self.screen, COL["panel"], R, border_radius=12)
        pygame.draw.rect(self.screen, COL["panel_edge"], R, 2, border_radius=12)
        draw_text(self.screen, "Controls", self.fonts["big"], COL["accent"], (R.x + 28, R.y + 18))
        y = R.y + 62
        for key, desc in HELP_LINES:
            draw_text(self.screen, key, self.fonts["normal"], COL["info"], (R.x + 28, y))
            draw_text(self.screen, desc, self.fonts["normal"], COL["text"], (R.x + 220, y))
            y += 30
        draw_text(self.screen, "Press any key or click to close", self.fonts["small"], COL["muted"],
                  (R.centerx, R.bottom - 34), "midtop")

    def draw(self):
        if self.state == "title":
            self.draw_title()
            pygame.display.flip()
            return
        if self.state == "race":
            self.race_screen.draw(self.screen, self.time)
            pygame.display.flip()
            return
        if self.state == "bench":
            self.bench_screen.draw(self.screen)
            pygame.display.flip()
            return
        self.screen.fill(COL["bg"])
        self.draw_grid()
        self.particles.draw(self.screen)
        if self.show_inspector:
            self.draw_inspector()
        self.draw_banner()
        self.draw_status()
        self.draw_chart()
        self.draw_panel()
        if self.show_dashboard:
            self.dashboard.draw(self.screen, self.fonts)
        if self.show_help:
            self.draw_help()
        pygame.display.flip()

    # ================================================================
    #  Main loop
    # ================================================================
    def run(self):
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
