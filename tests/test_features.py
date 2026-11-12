"""Tests for Race mode, Benchmark mode and the search trace used by the inspector.

All pure logic - no display, no pygame.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.benchmark import Benchmark                                    # noqa: E402
from game.dungeon import Dungeon                                         # noqa: E402
from game.levels import LEVELS                                           # noqa: E402
from game.race import MAX_RACERS, MIN_RACERS, Race                       # noqa: E402
from game.search import ALGORITHM_ORDER, run_algorithm                   # noqa: E402

TWIN = next(lv for lv in LEVELS if lv.name == "Twin Bridges")


def run_to_end(race, dt=0.1, speed=8):
    n = 0
    while not race.done and n < 200000:
        race.update(dt, speed)
        n += 1
    return n


class RaceTests(unittest.TestCase):
    def test_astar_beats_ucs_and_bfs_on_twin_bridges(self):
        race = Race(TWIN, ["BFS", "UCS", "A*"], 40, "manhattan")
        ranks = {r.name: r.rank for r in race.racers}
        self.assertEqual(ranks["A*"], 1)
        self.assertGreater(ranks["BFS"], ranks["A*"])
        self.assertGreater(ranks["UCS"], ranks["A*"])

    def test_finish_time_counts_expansions_and_walking(self):
        race = Race(TWIN, ["UCS", "A*"], 40, "manhattan")
        for r in race.racers:
            self.assertAlmostEqual(r.finish_ticks, r.total_expand + r.result.length * 5)

    def test_race_runs_to_completion_and_announces_each_racer_once(self):
        race = Race(TWIN, ["BFS", "DFS", "UCS", "A*"], 40, "manhattan")
        announced = []
        n = 0
        while not race.done and n < 100000:
            announced += [r.name for r in race.update(0.1, 8)]
            n += 1
        announced += [r.name for r in race.update(0.1, 8)]
        self.assertTrue(race.done)
        self.assertEqual(sorted(announced), ["A*", "BFS", "DFS", "UCS"])

    def test_cheapest_and_winners(self):
        race = Race(TWIN, ["BFS", "UCS", "A*"], 40, "manhattan")
        self.assertEqual(sorted(r.name for r in race.cheapest()), ["A*", "UCS"])
        self.assertEqual([r.name for r in race.winners()], ["A*"])
        self.assertEqual(race.best_cost, run_algorithm("UCS", TWIN).cost)

    def test_failed_racer_never_wins(self):
        race = Race(LEVELS[0], ["DLS", "A*"], 5, "manhattan")      # depth limit 5 cannot solve it
        dls = next(r for r in race.racers if r.name == "DLS")
        self.assertFalse(dls.result.found)
        self.assertIsNone(dls.rank)
        run_to_end(race)
        self.assertEqual([r.name for r in race.winners()], ["A*"])

    def test_pause_freezes_the_clock(self):
        race = Race(TWIN, ["BFS", "A*"], 40, "manhattan")
        race.update(0.1, 1)
        race.paused = True
        t = race.ticks
        race.update(1.0, 8)
        self.assertEqual(race.ticks, t)

    def test_frontier_replay_matches_recorded_sizes(self):
        race = Race(TWIN, ["BFS", "UCS", "A*", "DFS"], 40, "manhattan")
        race.jump_to_end()
        for r in race.racers:
            r.sync_frontier()
            sizes = r.result.frontier_sizes
            self.assertEqual(len(r.frontier), sizes[-1], r.name)

    def test_ids_replay_is_scaled_to_true_expansion_count(self):
        race = Race(TWIN, ["IDS", "A*"], 40, "manhattan")
        ids = next(r for r in race.racers if r.name == "IDS")
        self.assertGreater(ids.total_expand, len(ids.result.explored))   # cumulative > last pass
        ids.set_time(ids.total_expand)
        self.assertEqual(ids.shown, len(ids.result.explored))
        self.assertEqual(ids.expanded_count, ids.total_expand)

    def test_racer_count_is_validated(self):
        with self.assertRaises(ValueError):
            Race(TWIN, ["A*"], 40, "manhattan")
        with self.assertRaises(ValueError):
            Race(TWIN, ALGORITHM_ORDER[: MAX_RACERS + 1], 40, "manhattan")
        self.assertEqual((MIN_RACERS, MAX_RACERS), (2, 4))


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bench = Benchmark(count=8, seed=500)
        cls.bench.run_all()

    def test_runs_all_maps_and_algorithms(self):
        b = self.bench
        self.assertTrue(b.done)
        self.assertEqual(b.maps_done, 8)
        self.assertEqual(len(b.records), 8 * len(ALGORITHM_ORDER))

    def test_optimal_algorithms_are_optimal_on_every_map(self):
        s = self.bench.summary()
        for name in ("UCS", "A*"):
            self.assertEqual(s[name]["solved_pct"], 100.0)
            self.assertEqual(s[name]["optimal_pct"], 100.0)
            self.assertAlmostEqual(s[name]["cost_ratio"], 1.0)

    def test_nothing_beats_the_optimum(self):
        for name, m in self.bench.summary().items():
            if m["cost_ratio"] is not None:
                self.assertGreaterEqual(m["cost_ratio"], 1.0 - 1e-9, name)

    def test_astar_expands_no_more_nodes_than_ucs(self):
        s = self.bench.summary()
        self.assertLessEqual(s["A*"]["avg_expanded"], s["UCS"]["avg_expanded"])

    def test_same_seed_gives_same_results(self):
        again = Benchmark(count=3, seed=500)
        again.run_all()
        first = [(r["algorithm"], r["cost"], r["expanded"]) for r in self.bench.records[: 3 * 7]]
        second = [(r["algorithm"], r["cost"], r["expanded"]) for r in again.records]
        self.assertEqual(first, second)

    def test_incremental_stepping_and_progress(self):
        b = Benchmark(count=3, seed=1)
        self.assertEqual(b.progress, 0.0)
        b.step()
        self.assertAlmostEqual(b.progress, 1 / 3)
        b.run_all()
        self.assertEqual(b.progress, 1.0)
        b.step()                                  # extra steps after the end do nothing
        self.assertEqual(b.maps_done, 3)

    def test_insights_are_generated(self):
        lines = self.bench.insights()
        self.assertGreaterEqual(len(lines), 4)
        self.assertTrue(any("A*" in line for line in lines))

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.bench.save_csv(tmp)
            self.assertEqual(len(paths), 2)
            with open(paths[0], encoding="utf-8") as fh:
                self.assertEqual(len(fh.read().strip().splitlines()), 1 + len(ALGORITHM_ORDER))
            with open(paths[1], encoding="utf-8") as fh:
                self.assertEqual(len(fh.read().strip().splitlines()), 1 + len(self.bench.records))


class TraceTests(unittest.TestCase):
    def test_trace_lists_are_aligned(self):
        for d in LEVELS:
            for name in ALGORITHM_ORDER:
                r = run_algorithm(name, d, 200)
                n = len(r.explored)
                self.assertEqual(n, len(r.generated))
                self.assertEqual(n, len(r.child_g))
                self.assertEqual(n, len(r.exp_g))
                self.assertEqual(n, len(r.exp_parent))
                self.assertTrue(all(len(a) == len(b) for a, b in zip(r.generated, r.child_g)))
                self.assertIsNone(r.exp_parent[0])
                self.assertEqual(r.exp_g[0], 0)

    def test_expanded_g_was_recorded_when_the_state_was_generated(self):
        d = LEVELS[1]
        for name in ALGORITHM_ORDER:
            r = run_algorithm(name, d, 200)
            seen = {r.explored[0]: {0}}
            for i, state in enumerate(r.explored):
                self.assertIn(r.exp_g[i], seen.get(state, set()), f"{name} step {i}")
                for kid, g in zip(r.generated[i], r.child_g[i]):
                    seen.setdefault(kid, set()).add(g)

    def test_goal_g_equals_path_cost(self):
        for d in LEVELS:
            for name in ALGORITHM_ORDER:
                r = run_algorithm(name, d, 200)
                self.assertEqual(r.exp_g[-1], r.cost)

    def test_parent_of_goal_is_second_last_path_state(self):
        r = run_algorithm("A*", LEVELS[1])
        self.assertEqual(r.exp_parent[-1], r.path[-2])

    def test_heuristic_as_does_not_change_the_dungeon_setting(self):
        d = LEVELS[1]
        h = d.heuristic_as(d.start_state, "zero")
        self.assertEqual(h, 0)
        self.assertEqual(d.heuristic_mode, "manhattan")


if __name__ == "__main__":
    unittest.main()
