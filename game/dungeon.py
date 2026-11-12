"""Dungeon model: the grid, terrain costs and the search-problem formulation.

Search problem
--------------
* STATE      : (row, col, has_key)
* ACTIONS    : move Up / Right / Down / Left into a non-wall cell
* TRANSITION : entering the key cell sets has_key = True
* STEP COST  : terrain cost of the cell being entered (floor 1, mud 3, water 5)
* GOAL TEST  : the explorer stands on the treasure cell (only enterable with the key)
"""
import copy
import math
import random
from collections import deque
from typing import Iterator, List, Optional, Tuple

from .settings import FLOOR, MUD, TERRAIN_COST, WALL, WATER

State = Tuple[int, int, bool]

# Action order is also the tie-breaking order for the uninformed searches.
MOVES = [("Up", -1, 0), ("Right", 0, 1), ("Down", 1, 0), ("Left", 0, -1)]

# Heuristic choices (used by Greedy and A*). All except "weighted" are admissible.
HEURISTICS = ["manhattan", "euclidean", "chebyshev", "zero", "weighted"]
HEURISTIC_LABELS = {
    "manhattan": "Manhattan",
    "euclidean": "Euclidean",
    "chebyshev": "Chebyshev",
    "zero": "Zero (h=0)",
    "weighted": "Manhattan x3*",
}
ADMISSIBLE = {"manhattan", "euclidean", "chebyshev", "zero"}

BRUSH_TERRAIN = {"wall": WALL, "floor": FLOOR, "mud": MUD, "water": WATER}
MARKERS = ("start", "key", "goal")
MARKER_NAMES = {"start": "start", "key": "key", "goal": "treasure"}


class Dungeon:
    def __init__(self, rows: List[str], name: str = "Custom"):
        lines = [r.rstrip("\n") for r in rows if r.strip("\n") != ""]
        self.name = name
        self.height = len(lines)
        self.width = max(len(line) for line in lines)
        self.terrain: List[List[str]] = []
        self.start: Optional[Tuple[int, int]] = None
        self.key: Optional[Tuple[int, int]] = None
        self.goal: Optional[Tuple[int, int]] = None
        self.heuristic_mode = "manhattan"
        self.override_start: Optional[State] = None   # used for hints from mid-game

        for r, line in enumerate(lines):
            row = []
            for c in range(self.width):
                ch = line[c] if c < len(line) else WALL
                if ch == "S":
                    self.start, ch = (r, c), FLOOR
                elif ch == "K":
                    self.key, ch = (r, c), FLOOR
                elif ch == "T":
                    self.goal, ch = (r, c), FLOOR
                elif ch not in (WALL, FLOOR, MUD, WATER):
                    ch = FLOOR
                row.append(ch)
            self.terrain.append(row)

        if not (self.start and self.key and self.goal):
            raise ValueError(f"Dungeon '{name}' needs S (start), K (key) and T (treasure)")

    # ------------------------------------------------------------ basics
    @property
    def start_state(self) -> State:
        if self.override_start is not None:
            return self.override_start
        return (self.start[0], self.start[1], False)

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.height and 0 <= c < self.width

    def is_wall(self, r: int, c: int) -> bool:
        return not self.in_bounds(r, c) or self.terrain[r][c] == WALL

    def cost_of(self, r: int, c: int) -> int:
        return TERRAIN_COST[self.terrain[r][c]]

    # --------------------------------------------------- problem interface
    def step(self, state: State, dr: int, dc: int) -> Optional[Tuple[State, int]]:
        """Try to move one cell. Returns (new_state, cost) or None if blocked."""
        r, c, has_key = state
        nr, nc = r + dr, c + dc
        if self.is_wall(nr, nc):
            return None
        if (nr, nc) == self.goal and not has_key:      # locked treasure chamber
            return None
        new_key = has_key or (nr, nc) == self.key
        return (nr, nc, new_key), self.cost_of(nr, nc)

    def successors(self, state: State) -> Iterator[Tuple[State, int]]:
        for _name, dr, dc in MOVES:
            result = self.step(state, dr, dc)
            if result is not None:
                yield result

    def is_goal(self, state: State) -> bool:
        return (state[0], state[1]) == self.goal

    def _dist(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
        mode = self.heuristic_mode
        if mode == "euclidean":
            return math.hypot(dr, dc)
        if mode == "chebyshev":
            return max(dr, dc)
        if mode == "weighted":
            return 3 * (dr + dc)
        return dr + dc                              # manhattan

    def heuristic(self, state: State) -> float:
        """Key-aware heuristic. Without the key the explorer must visit the key
        first and then the treasure, so h = d(pos, key) + d(key, goal).

        Every step costs at least 1, so manhattan / euclidean / chebyshev / zero
        never over-estimate (admissible). "weighted" (x3) deliberately does.
        """
        if self.heuristic_mode == "zero":
            return 0
        pos = (state[0], state[1])
        if state[2]:
            return self._dist(pos, self.goal)
        return self._dist(pos, self.key) + self._dist(self.key, self.goal)

    def heuristic_as(self, state: State, mode: str) -> float:
        """Evaluate the heuristic in a given mode without changing the dungeon's setting."""
        old = self.heuristic_mode
        self.heuristic_mode = mode
        try:
            return self.heuristic(state)
        finally:
            self.heuristic_mode = old

    # ------------------------------------------------------------ helpers
    def marker_at(self, r: int, c: int) -> Optional[str]:
        for name in MARKERS:
            if getattr(self, name) == (r, c):
                return name
        return None

    def paint(self, r: int, c: int, brush: str):
        """Map-editor operation. Returns (changed_cells, message)."""
        if not self.in_bounds(r, c):
            return [], ""
        here = self.marker_at(r, c)
        if brush in BRUSH_TERRAIN:
            terrain = BRUSH_TERRAIN[brush]
            if here and terrain != FLOOR:
                return [], f"Move the {MARKER_NAMES[here]} first - it sits on this cell."
            if self.terrain[r][c] == terrain:
                return [], ""
            self.terrain[r][c] = terrain
            return [(r, c)], ""
        if brush in MARKERS:
            if here == brush:
                return [], ""
            if here:
                return [], f"The {MARKER_NAMES[here]} is already on that cell."
            old = getattr(self, brush)
            self.terrain[r][c] = FLOOR
            setattr(self, brush, (r, c))
            return [old, (r, c)], ""
        return [], ""

    def clone(self, name: Optional[str] = None) -> "Dungeon":
        twin = copy.deepcopy(self)
        if name:
            twin.name = name
        return twin

    def count_floor_cells(self) -> int:
        return sum(1 for row in self.terrain for ch in row if ch != WALL)

    def __repr__(self) -> str:  # handy for debugging
        return f"Dungeon({self.name!r}, {self.width}x{self.height})"


# ====================================================================
#  Random dungeon generator (recursive back-tracker maze + extras)
# ====================================================================
def random_dungeon(width: int = 25, height: int = 17, seed: Optional[int] = None) -> Dungeon:
    """Generate a random, always-solvable dungeon.

    A perfect maze guarantees every floor cell is connected; we then knock
    out some walls (creating loops, so algorithms behave differently) and
    paint blobs of mud and water on top.
    """
    rng = random.Random(seed)
    width += (width % 2 == 0)       # need odd sizes for the maze carver
    height += (height % 2 == 0)
    grid = [[WALL] * width for _ in range(height)]

    # --- recursive back-tracker (iterative version)
    stack = [(1, 1)]
    grid[1][1] = FLOOR
    while stack:
        r, c = stack[-1]
        options = []
        for _n, dr, dc in MOVES:
            nr, nc = r + 2 * dr, c + 2 * dc
            if 1 <= nr < height - 1 and 1 <= nc < width - 1 and grid[nr][nc] == WALL:
                options.append((nr, nc, r + dr, c + dc))
        if not options:
            stack.pop()
            continue
        nr, nc, wr, wc = rng.choice(options)
        grid[wr][wc] = FLOOR
        grid[nr][nc] = FLOOR
        stack.append((nr, nc))

    # --- knock out some walls to create loops
    for r in range(1, height - 1):
        for c in range(1, width - 1):
            if grid[r][c] != WALL:
                continue
            horizontal = grid[r][c - 1] != WALL and grid[r][c + 1] != WALL
            vertical = grid[r - 1][c] != WALL and grid[r + 1][c] != WALL
            if (horizontal or vertical) and rng.random() < 0.18:
                grid[r][c] = FLOOR

    # --- terrain blobs
    floor_cells = [(r, c) for r in range(height) for c in range(width) if grid[r][c] == FLOOR]
    for _ in range(max(4, (width * height) // 60)):
        cr, cc = rng.choice(floor_cells)
        kind = rng.choice([MUD, MUD, WATER])
        radius = rng.choice([1, 2, 2])
        for r in range(cr - radius, cr + radius + 1):
            for c in range(cc - radius, cc + radius + 1):
                if (0 < r < height - 1 and 0 < c < width - 1 and grid[r][c] == FLOOR
                        and abs(r - cr) + abs(c - cc) <= radius and rng.random() < 0.85):
                    grid[r][c] = kind

    # --- place start / goal in opposite corners, key somewhere in between
    start, goal = (1, 1), (height - 2, width - 2)
    grid[start[0]][start[1]] = FLOOR
    grid[goal[0]][goal[1]] = FLOOR
    candidates = [
        p for p in floor_cells
        if p != start and p != goal
        and abs(p[0] - start[0]) + abs(p[1] - start[1]) > (width + height) // 4
        and abs(p[0] - goal[0]) + abs(p[1] - goal[1]) > (width + height) // 6
    ] or [p for p in floor_cells if p not in (start, goal)]
    key = rng.choice(candidates)
    grid[key[0]][key[1]] = FLOOR

    marked = [list("".join(row)) for row in grid]
    marked[start[0]][start[1]] = "S"
    marked[key[0]][key[1]] = "K"
    marked[goal[0]][goal[1]] = "T"
    return Dungeon(["".join(r) for r in marked], name=f"Random (seed {seed})")


def is_solvable(dungeon: Dungeon) -> bool:
    """Plain BFS reachability check (used by tests and the generator)."""
    start = dungeon.start_state
    seen = {start}
    queue = deque([start])
    while queue:
        s = queue.popleft()
        if dungeon.is_goal(s):
            return True
        for ns, _c in dungeon.successors(s):
            if ns not in seen:
                seen.add(ns)
                queue.append(ns)
    return False
