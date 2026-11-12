"""Algorithm Race - pure logic (no pygame), so it can be unit-tested.

Several algorithms solve the SAME dungeon at the same time. Every racer is
driven by one shared clock measured in "ticks":

* exploring : 1 tick = 1 node expansion          (so fewer expansions = faster)
* walking   : 1 step of the final path = WALK_TICKS_PER_STEP ticks

The finishing order is therefore decided by how much work the algorithm did
(expansions) plus how long its path is - exactly the trade-off the course is about.
"""
from typing import List, Optional

from . import settings as S
from .search import SearchResult, run_algorithm

TICKS_PER_SECOND = float(S.EXPLORE_NODES_PER_SEC)                 # at speed x1
WALK_TICKS_PER_STEP = S.EXPLORE_NODES_PER_SEC / S.WALK_STEPS_PER_SEC

MIN_RACERS, MAX_RACERS = 2, 4


class Racer:
    def __init__(self, name: str, result: SearchResult, start_state):
        self.name = name
        self.result = result
        self.start_state = start_state
        self.total_expand = max(1, result.expanded)
        self.walk_ticks = result.length * WALK_TICKS_PER_STEP if result.found else 0.0
        self.finish_ticks = self.total_expand + self.walk_ticks
        self.ticks = 0.0
        self.rank: Optional[int] = None          # 1 = first to reach the treasure
        # replay state for the frontier overlay
        self.frontier = {start_state}
        self._expanded = set()
        self._pos = 0

    # ------------------------------------------------------------ derived
    @property
    def finished(self) -> bool:
        return self.ticks >= self.finish_ticks

    @property
    def phase(self) -> str:
        if self.ticks < self.total_expand:
            return "exploring"
        if self.result.found and self.ticks < self.finish_ticks:
            return "walking"
        return "finished"

    @property
    def expanded_count(self) -> int:
        """True number of expansions so far (for IDS this is the cumulative count)."""
        return int(min(self.ticks, self.total_expand))

    @property
    def shown(self) -> int:
        """How many entries of result.explored are visible (IDS replays only its last pass)."""
        n = len(self.result.explored)
        return int(min(self.ticks, self.total_expand) / self.total_expand * n)

    @property
    def walk_index(self) -> float:
        if not self.result.found:
            return 0.0
        pos = max(0.0, (self.ticks - self.total_expand) / WALK_TICKS_PER_STEP)
        return min(pos, float(self.result.length))

    @property
    def finish_seconds(self) -> float:
        return self.finish_ticks / TICKS_PER_SECOND

    def set_time(self, ticks: float) -> None:
        self.ticks = min(ticks, self.finish_ticks)

    def sync_frontier(self) -> None:
        """Advance the frontier replay up to the currently visible expansion."""
        res = self.result
        target = self.shown
        while self._pos < target:
            i = self._pos
            self.frontier.discard(res.explored[i])
            self._expanded.add(res.explored[i])
            for kid in res.generated[i]:
                if kid not in self._expanded:
                    self.frontier.add(kid)
            self._pos += 1

    def frontier_size_now(self) -> int:
        sizes = self.result.frontier_sizes
        if not sizes or self.shown == 0:
            return 1
        return sizes[min(self.shown, len(sizes)) - 1]


class Race:
    def __init__(self, dungeon, names: List[str], depth_limit: int, heuristic: str):
        if not MIN_RACERS <= len(names) <= MAX_RACERS:
            raise ValueError(f"A race needs {MIN_RACERS}-{MAX_RACERS} algorithms")
        self.dungeon = dungeon
        start = dungeon.start_state
        self.racers = [Racer(n, run_algorithm(n, dungeon, depth_limit, heuristic=heuristic), start)
                       for n in names]
        self.ticks = 0.0
        self.paused = False
        self._announced = set()

        found = [r for r in self.racers if r.result.found]
        for r in found:
            r.rank = 1 + sum(1 for o in found if o.finish_ticks < r.finish_ticks)
        self.best_cost = min((r.result.cost for r in found), default=None)
        self.max_finish = max(r.finish_ticks for r in self.racers)

    # ----------------------------------------------------------- results
    @property
    def done(self) -> bool:
        return all(r.finished for r in self.racers)

    def winners(self) -> List[Racer]:
        """Racers that reached the treasure first (ties share the title)."""
        return [r for r in self.racers if r.rank == 1]

    def cheapest(self) -> List[Racer]:
        return [r for r in self.racers if r.result.found and r.result.cost == self.best_cost]

    # ------------------------------------------------------------ update
    def update(self, dt: float, speed: float = 1.0) -> List[Racer]:
        """Advance the shared clock. Returns the racers that finished during this call."""
        newly = []
        if not self.paused and not self.done:
            self.ticks += TICKS_PER_SECOND * speed * dt
            for r in self.racers:
                r.set_time(self.ticks)
        for r in self.racers:
            if r.finished and r.name not in self._announced:
                self._announced.add(r.name)
                newly.append(r)
        return newly

    def jump_to_end(self) -> None:
        self.ticks = self.max_finish
        for r in self.racers:
            r.set_time(self.ticks)
