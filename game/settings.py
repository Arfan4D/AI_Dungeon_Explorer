"""Global constants: window layout, colours and terrain costs."""

# ----------------------------------------------------------------- window
WINDOW_W, WINDOW_H = 1216, 720
FPS = 60

# (x, y, w, h) tuples - converted to pygame.Rect inside game.py / ui.py
GRID_AREA = (16, 16, 800, 544)
STATUS_AREA = (16, 572, 800, 52)
CHART_AREA = (16, 634, 800, 70)
PANEL_AREA = (832, 16, 368, 688)

# ---------------------------------------------------------------- terrain
WALL = "#"
FLOOR = "."
MUD = "~"
WATER = "w"

# Cost of ENTERING a cell of the given terrain.
TERRAIN_COST = {FLOOR: 1, MUD: 3, WATER: 5}

# --------------------------------------------------------------- colours
COLORS = {
    "bg": (18, 16, 24),
    "panel": (30, 27, 40),
    "panel_edge": (70, 62, 96),
    "text": (232, 228, 240),
    "muted": (150, 144, 170),
    "accent": (255, 196, 70),
    "good": (96, 214, 130),
    "bad": (232, 92, 92),
    "info": (92, 200, 232),

    "floor_a": (78, 72, 94),
    "floor_b": (72, 66, 88),
    "wall": (30, 26, 38),
    "wall_line": (44, 38, 56),
    "mud": (112, 78, 46),
    "mud_dot": (82, 56, 32),
    "water": (40, 96, 170),
    "water_line": (100, 160, 230),

    "explored": (80, 140, 255),        # explored without the key
    "explored_key": (190, 110, 255),   # explored while carrying the key
    "frontier": (255, 150, 60),
    "hint": (130, 255, 160),
    "path": (255, 214, 64),

    "start": (90, 220, 130),
    "key": (255, 214, 64),
    "chest": (176, 112, 52),
    "chest_band": (255, 196, 70),
    "lock": (220, 70, 70),
    "explorer": (60, 220, 200),

    "button": (52, 46, 74),
    "button_hover": (72, 64, 104),
    "button_sel": (255, 176, 40),
    "button_off": (38, 34, 52),
}

# Animation speed multipliers (index chosen in the side panel)
SPEED_STEPS = [0.5, 1, 2, 4, 8, 16, 32]
EXPLORE_NODES_PER_SEC = 40   # at speed x1
WALK_STEPS_PER_SEC = 8       # at speed x1

DEFAULT_DEPTH_LIMIT = 40
MAX_DEPTH_LIMIT = 200

# ------------------------------------------------------------------ team
COURSE = "CSE 366 - Artificial Intelligence"
DEPARTMENT = "Department of Computer Science and Engineering"
GROUP = "Group 07"
TEAM = [
    ("Momin Khair Arfan", "2023-2-60-041"),
    ("Sakibull Hasan Sakib", "2023-2-60-039"),
    ("Farhana Forhad Mim", "2023-2-60-276"),
]
