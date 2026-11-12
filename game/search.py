"""Search algorithms for the dungeon.

Every algorithm works on the Dungeon problem interface and returns a
SearchResult, so the game, the dashboard and the unit tests treat them all
the same way.

All algorithms test for the goal when a node is EXPANDED (popped), so the
"expanded nodes" metric is directly comparable between them.

Besides the final path, each run records, for every expansion, which child
states were added to the frontier. From that the GUI can replay the search
step by step (frontier overlay + frontier-size chart) and we can report the
peak frontier size (a measure of memory use).
"""
import heapq
from collections import deque
from dataclasses import dataclass, field
from itertools import count
from time import perf_counter
from typing import Callable, Dict, List, Optional

from .dungeon import Dungeon, State
from .settings import DEFAULT_DEPTH_LIMIT

SUCCESS = "success"
FAILURE = "failure"
DEPTH_LIMIT = "depth_limit"      # search stopped because of the depth cut-off


# ====================================================================
#  Data structures
# ====================================================================
class Node:
    """A search-tree node (state + bookkeeping)."""
    __slots__ = ("state", "parent", "g", "depth")

    def __init__(self, state: State, parent: Optional["Node"], g: int, depth: int):
        self.state = state
        self.parent = parent
        self.g = g              # accumulated path cost
        self.depth = depth      # number of steps from the start


@dataclass
class SearchResult:
    algorithm: str
    status: str                                   # SUCCESS / FAILURE / DEPTH_LIMIT
    path: List[State] = field(default_factory=list)
    cost: float = 0
    expanded: int = 0
    explored: List[State] = field(default_factory=list)          # expansion order
    generated: List[List[State]] = field(default_factory=list)   # children added per expansion
    child_g: List[List[float]] = field(default_factory=list)     # g-value of each generated child
    exp_g: List[float] = field(default_factory=list)             # g-value of each expanded node
    exp_parent: List[Optional[State]] = field(default_factory=list)  # parent state of each expanded node
    frontier_sizes: List[int] = field(default_factory=list)      # frontier size after each expansion
    time_ms: float = 0.0
    depth_limit: Optional[int] = None

    @property
    def length(self) -> int:
        """Path length in steps."""
        return max(len(self.path) - 1, 0)

    @property
    def found(self) -> bool:
        return self.status == SUCCESS

    @property
    def max_frontier(self) -> int:
        """Peak number of waiting states - a proxy for memory usage."""
        return max(self.frontier_sizes, default=0)


class Trace:
    """Records every expansion so the GUI can replay the search step by step."""
    __slots__ = ("explored", "generated", "child_g", "exp_g", "exp_parent", "_kids", "_kid_g")

    def __init__(self):
        self.explored: List[State] = []
        self.generated: List[List[State]] = []
        self.child_g: List[List[float]] = []
        self.exp_g: List[float] = []
        self.exp_parent: List[Optional[State]] = []
        self._kids: List[State] = []
        self._kid_g: List[float] = []

    def expand(self, node: "Node") -> None:
        self.explored.append(node.state)
        self.exp_g.append(node.g)
        self.exp_parent.append(node.parent.state if node.parent is not None else None)
        self._kids, self._kid_g = [], []
        self.generated.append(self._kids)
        self.child_g.append(self._kid_g)

    def add(self, state: State, g: float) -> None:
        """Record a child that was put on the frontier by the current expansion."""
        self._kids.append(state)
        self._kid_g.append(g)


def frontier_profile(start: State, explored: List[State], generated: List[List[State]]) -> List[int]:
    """Replay a search and return the frontier size after every expansion.

    The GUI uses exactly the same replay logic to colour the frontier cells.
    """
    frontier = {start}
    expanded = set()
    sizes = []
    for state, kids in zip(explored, generated):
        frontier.discard(state)
        expanded.add(state)
        for k in kids:
            if k not in expanded:
                frontier.add(k)
        sizes.append(len(frontier))
    return sizes


def _path_from(node: Node) -> List[State]:
    states = []
    while node is not None:
        states.append(node.state)
        node = node.parent
    states.reverse()
    return states


def _result(name: str, t0: float, status: str, node: Optional[Node], expanded: int,
            trace: Trace, start: State, limit: Optional[int] = None) -> SearchResult:
    return SearchResult(
        algorithm=name,
        status=status,
        path=_path_from(node) if node is not None else [],
        cost=node.g if node is not None else 0,
        expanded=expanded,
        explored=trace.explored,
        generated=trace.generated,
        child_g=trace.child_g,
        exp_g=trace.exp_g,
        exp_parent=trace.exp_parent,
        frontier_sizes=frontier_profile(start, trace.explored, trace.generated),
        time_ms=(perf_counter() - t0) * 1000.0,
        depth_limit=limit,
    )


# ====================================================================
#  Uninformed search
# ====================================================================
def bfs(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Breadth-First Search - FIFO queue. Fewest steps (not lowest cost)."""
    t0 = perf_counter()
    root = Node(d.start_state, None, 0, 0)
    frontier = deque([root])
    reached = {root.state}
    tr = Trace()
    expanded = 0
    while frontier:
        node = frontier.popleft()
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return _result("BFS", t0, SUCCESS, node, expanded, tr, root.state)
        for ns, c in d.successors(node.state):
            if ns not in reached:
                reached.add(ns)
                frontier.append(Node(ns, node, node.g + c, node.depth + 1))
                tr.add(ns, node.g + c)
    return _result("BFS", t0, FAILURE, None, expanded, tr, root.state)


def dfs(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Depth-First Search - LIFO stack. Fast to dive, but paths can be long."""
    t0 = perf_counter()
    root = Node(d.start_state, None, 0, 0)
    stack = [root]
    visited = set()
    tr = Trace()
    expanded = 0
    while stack:
        node = stack.pop()
        if node.state in visited:
            continue
        visited.add(node.state)
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return _result("DFS", t0, SUCCESS, node, expanded, tr, root.state)
        # reversed so that the first action (Up) is explored first
        for ns, c in reversed(list(d.successors(node.state))):
            if ns not in visited:
                stack.append(Node(ns, node, node.g + c, node.depth + 1))
                tr.add(ns, node.g + c)
    return _result("DFS", t0, FAILURE, None, expanded, tr, root.state)


def ucs(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Uniform-Cost Search - priority queue ordered by g(n). Optimal cost."""
    t0 = perf_counter()
    tie = count()
    root = Node(d.start_state, None, 0, 0)
    frontier = [(0, next(tie), root)]
    best_g = {root.state: 0}
    tr = Trace()
    expanded = 0
    while frontier:
        g, _t, node = heapq.heappop(frontier)
        if g > best_g.get(node.state, float("inf")):
            continue                      # stale queue entry
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return _result("UCS", t0, SUCCESS, node, expanded, tr, root.state)
        for ns, c in d.successors(node.state):
            ng = g + c
            if ng < best_g.get(ns, float("inf")):
                best_g[ns] = ng
                heapq.heappush(frontier, (ng, next(tie), Node(ns, node, ng, node.depth + 1)))
                tr.add(ns, ng)
    return _result("UCS", t0, FAILURE, None, expanded, tr, root.state)


def _depth_limited(d: Dungeon, limit: int):
    """Core of DLS. Returns (status, node, expanded, trace).

    status is 'success', 'cutoff' (limit was hit) or 'failure' (exhausted).
    A state is re-expanded only if it is reached at a shallower depth than
    before, which keeps the search finite while staying correct.
    """
    root = Node(d.start_state, None, 0, 0)
    stack = [root]
    best_depth = {root.state: 0}
    tr = Trace()
    expanded = 0
    cutoff = False
    while stack:
        node = stack.pop()
        if best_depth.get(node.state, 1 << 30) < node.depth:
            continue                      # a shallower route was found meanwhile
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return "success", node, expanded, tr
        if node.depth >= limit:
            cutoff = True
            continue
        for ns, c in reversed(list(d.successors(node.state))):
            nd = node.depth + 1
            if best_depth.get(ns, 1 << 30) <= nd:
                continue
            best_depth[ns] = nd
            stack.append(Node(ns, node, node.g + c, nd))
            tr.add(ns, node.g + c)
    return ("cutoff" if cutoff else "failure"), None, expanded, tr


def dls(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Depth-Limited Search - DFS that never goes deeper than `depth_limit`."""
    t0 = perf_counter()
    limit = DEFAULT_DEPTH_LIMIT if depth_limit is None else depth_limit
    start = d.start_state
    status, node, expanded, tr = _depth_limited(d, limit)
    if status == "success":
        return _result("DLS", t0, SUCCESS, node, expanded, tr, start, limit)
    final = DEPTH_LIMIT if status == "cutoff" else FAILURE
    return _result("DLS", t0, final, None, expanded, tr, start, limit)


def ids(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Iterative Deepening Search - DLS with limit 0, 1, 2, ... until solved.

    `expanded` counts the nodes of ALL iterations; the replay data (explored,
    generated, frontier) only keeps the last iteration so it stays readable.
    """
    t0 = perf_counter()
    start = d.start_state
    max_depth = d.width * d.height * 2          # safe upper bound on solution depth
    total_expanded = 0
    tr = Trace()
    limit = 0
    while limit <= max_depth:
        status, node, expanded, tr = _depth_limited(d, limit)
        total_expanded += expanded
        if status == "success":
            return _result("IDS", t0, SUCCESS, node, total_expanded, tr, start, limit)
        if status == "failure":                  # whole space exhausted: no solution
            return _result("IDS", t0, FAILURE, None, total_expanded, tr, start, limit)
        limit += 1
    return _result("IDS", t0, DEPTH_LIMIT, None, total_expanded, tr, start, max_depth)


# ====================================================================
#  Informed search
# ====================================================================
def greedy(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """Greedy Best-First Search - priority queue ordered by h(n) only."""
    t0 = perf_counter()
    tie = count()
    root = Node(d.start_state, None, 0, 0)
    frontier = [(d.heuristic(root.state), next(tie), root)]
    reached = {root.state}
    tr = Trace()
    expanded = 0
    while frontier:
        _h, _t, node = heapq.heappop(frontier)
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return _result("Greedy", t0, SUCCESS, node, expanded, tr, root.state)
        for ns, c in d.successors(node.state):
            if ns not in reached:
                reached.add(ns)
                heapq.heappush(frontier, (d.heuristic(ns), next(tie),
                                          Node(ns, node, node.g + c, node.depth + 1)))
                tr.add(ns, node.g + c)
    return _result("Greedy", t0, FAILURE, None, expanded, tr, root.state)


def astar(d: Dungeon, depth_limit: Optional[int] = None) -> SearchResult:
    """A* Search - priority queue ordered by f(n) = g(n) + h(n)."""
    t0 = perf_counter()
    tie = count()
    root = Node(d.start_state, None, 0, 0)
    frontier = [(d.heuristic(root.state), 0, next(tie), root)]
    best_g = {root.state: 0}
    tr = Trace()
    expanded = 0
    while frontier:
        _f, _h, _t, node = heapq.heappop(frontier)
        if node.g > best_g.get(node.state, float("inf")):
            continue                      # stale queue entry
        tr.expand(node)
        expanded += 1
        if d.is_goal(node.state):
            return _result("A*", t0, SUCCESS, node, expanded, tr, root.state)
        for ns, c in d.successors(node.state):
            ng = node.g + c
            if ng < best_g.get(ns, float("inf")):
                best_g[ns] = ng
                h = d.heuristic(ns)
                heapq.heappush(frontier, (ng + h, h, next(tie),
                                          Node(ns, node, ng, node.depth + 1)))
                tr.add(ns, ng)
    return _result("A*", t0, FAILURE, None, expanded, tr, root.state)


# ====================================================================
#  Registry used by the GUI
# ====================================================================
ALGORITHMS: Dict[str, Callable[..., SearchResult]] = {
    "BFS": bfs,
    "DFS": dfs,
    "UCS": ucs,
    "DLS": dls,
    "IDS": ids,
    "Greedy": greedy,
    "A*": astar,
}

FULL_NAMES = {
    "BFS": "Breadth-First Search",
    "DFS": "Depth-First Search",
    "UCS": "Uniform-Cost Search",
    "DLS": "Depth-Limited Search",
    "IDS": "Iterative Deepening Search",
    "Greedy": "Greedy Best-First Search",
    "A*": "A* Search",
}

# Short teaching notes shown in the side panel.
INFO = {
    "BFS": ("Expands the shallowest node first using a FIFO queue.",
            "Yes", "Fewest steps", "O(b^d)", "O(b^d)"),
    "DFS": ("Dives down one branch at a time using a LIFO stack.",
            "Yes (graph search)", "No", "O(b^m)", "O(b*m)"),
    "UCS": ("Always expands the node with the lowest path cost g(n).",
            "Yes", "Lowest cost", "O(b^(C*/e))", "O(b^(C*/e))"),
    "DLS": ("DFS that refuses to go deeper than the depth limit L.",
            "Only if L >= d", "No", "O(b^L)", "O(b*L)"),
    "IDS": ("Repeats DLS with limit 0, 1, 2... Combines BFS and DFS.",
            "Yes", "Fewest steps", "O(b^d)", "O(b*d)"),
    "Greedy": ("Follows the heuristic h(n) only and ignores the cost so far.",
               "Yes (graph search)", "No", "O(b^m)", "O(b^m)"),
    "A*": ("Expands the lowest f(n) = g(n) + h(n). Uses cost AND guidance.",
           "Yes", "Lowest cost*", "exp. in h error", "exp. in h error"),
}

# How each algorithm picks the next node (used by the inspector's queue panel).
QUEUE_RULE = {
    "BFS": ("FIFO queue", "oldest first"),
    "DFS": ("LIFO stack", "newest first"),
    "UCS": ("Priority queue", "lowest g first"),
    "DLS": ("LIFO stack", "newest first"),
    "IDS": ("LIFO stack", "newest first"),
    "Greedy": ("Priority queue", "lowest h first"),
    "A*": ("Priority queue", "lowest f = g + h first"),
}

UNINFORMED = ["BFS", "DFS", "UCS", "DLS", "IDS"]
INFORMED = ["Greedy", "A*"]
ALGORITHM_ORDER = UNINFORMED + INFORMED


def run_algorithm(name: str, dungeon: Dungeon, depth_limit: int = DEFAULT_DEPTH_LIMIT,
                  heuristic: Optional[str] = None,
                  start: Optional[State] = None) -> SearchResult:
    """Run one algorithm.

    heuristic - heuristic mode for Greedy / A* (see dungeon.HEURISTICS)
    start     - search from this state instead of the dungeon's start
                (used for hints during manual play)
    """
    old_mode, old_start = dungeon.heuristic_mode, dungeon.override_start
    try:
        if heuristic is not None:
            dungeon.heuristic_mode = heuristic
        dungeon.override_start = start
        return ALGORITHMS[name](dungeon, depth_limit)
    finally:
        dungeon.heuristic_mode, dungeon.override_start = old_mode, old_start
