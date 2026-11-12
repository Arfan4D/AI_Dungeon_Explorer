"""Unit tests for the search algorithms (run: python -m unittest discover tests -v).

These tests need no display and no pygame - the search code is completely
independent from the game interface.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.dungeon import (ADMISSIBLE, HEURISTICS, Dungeon, is_solvable,   # noqa: E402
                          random_dungeon)
from game.levels import LEVELS                                          # noqa: E402
from game.search import (ALGORITHM_ORDER, DEPTH_LIMIT, FAILURE, SUCCESS,  # noqa: E402
                         frontier_profile, run_algorithm)

TINY = [
    "#######",
    "#S.K..#",
    "#.###.#",
    "#....T#",
    "#######",
]

UNREACHABLE = [      # the treasure is walled off completely
    "#######",
    "#S.K#T#",
    "#######",
]

COST_TRAP = [        # straight route is mud, the detour is slightly longer but cheaper
    "#########",
    "#SK~~~..#",
    "#.#####.#",
    "#.......#",
    "#######T#",
    "#########",
]


def validate_path(test, dungeon, result):
    """A returned path must be a legal sequence of moves from start to goal."""
    path = result.path
    test.assertEqual(path[0], dungeon.start_state)
    test.assertTrue(dungeon.is_goal(path[-1]))
    total = 0
    for a, b in zip(path, path[1:]):
        options = dict(dungeon.successors(a))
        test.assertIn(b, options, f"illegal move {a} -> {b}")
        total += options[b]
    test.assertEqual(total, result.cost)
    test.assertTrue(path[-1][2], "treasure reached without the key")


class SearchTests(unittest.TestCase):
    def test_every_algorithm_solves_tiny_dungeon(self):
        d = Dungeon(TINY, "tiny")
        for name in ALGORITHM_ORDER:
            res = run_algorithm(name, d, depth_limit=50)
            self.assertEqual(res.status, SUCCESS, name)
            validate_path(self, d, res)

    def test_every_algorithm_solves_every_level(self):
        for d in LEVELS:
            self.assertTrue(is_solvable(d), d.name)
            for name in ALGORITHM_ORDER:
                res = run_algorithm(name, d, depth_limit=200)
                self.assertEqual(res.status, SUCCESS, f"{name} on {d.name}")
                validate_path(self, d, res)

    def test_optimal_algorithms_agree_on_cost(self):
        for d in LEVELS:
            ucs = run_algorithm("UCS", d)
            astar = run_algorithm("A*", d)
            self.assertEqual(ucs.cost, astar.cost, d.name)
            for name in ALGORITHM_ORDER:
                res = run_algorithm(name, d, depth_limit=200)
                self.assertGreaterEqual(res.cost, ucs.cost, f"{name} beat UCS on {d.name}")

    def test_bfs_and_ids_find_fewest_steps(self):
        for d in LEVELS:
            bfs = run_algorithm("BFS", d)
            ids = run_algorithm("IDS", d)
            self.assertEqual(bfs.length, ids.length, d.name)
            for name in ALGORITHM_ORDER:
                res = run_algorithm(name, d, depth_limit=200)
                self.assertGreaterEqual(res.length, bfs.length, f"{name} on {d.name}")

    def test_ucs_prefers_cheap_detour_over_shortest_path(self):
        d = Dungeon(COST_TRAP, "trap")
        bfs, ucs, astar = (run_algorithm(n, d) for n in ("BFS", "UCS", "A*"))
        self.assertLess(ucs.cost, bfs.cost)
        self.assertEqual(ucs.cost, astar.cost)

    def test_astar_expands_fewer_nodes_than_ucs(self):
        for d in LEVELS:
            self.assertLess(run_algorithm("A*", d).expanded, run_algorithm("UCS", d).expanded, d.name)

    def test_no_solution_reports_failure(self):
        d = Dungeon(UNREACHABLE, "blocked")
        self.assertFalse(is_solvable(d))
        for name in ("BFS", "DFS", "UCS", "IDS", "Greedy", "A*"):
            res = run_algorithm(name, d)
            self.assertEqual(res.status, FAILURE, name)
            self.assertEqual(res.path, [])

    def test_dls_reports_depth_limit(self):
        d = Dungeon(TINY, "tiny")
        self.assertEqual(run_algorithm("DLS", d, depth_limit=3).status, DEPTH_LIMIT)
        self.assertEqual(run_algorithm("DLS", d, depth_limit=30).status, SUCCESS)

    def test_dls_on_unreachable_map_is_plain_failure_when_limit_is_large(self):
        d = Dungeon(UNREACHABLE, "blocked")
        self.assertEqual(run_algorithm("DLS", d, depth_limit=50).status, FAILURE)

    def test_dls_path_never_exceeds_limit(self):
        d = LEVELS[1]
        res = run_algorithm("DLS", d, depth_limit=60)
        self.assertEqual(res.status, SUCCESS)
        self.assertLessEqual(res.length, 60)

    def test_locked_chamber_requires_key(self):
        d = Dungeon(TINY, "tiny")
        # standing next to the treasure WITHOUT the key must not allow entry
        self.assertIsNone(d.step((3, 4, False), 0, 1))
        self.assertIsNotNone(d.step((3, 4, True), 0, 1))

    def test_key_is_picked_up_when_entered(self):
        d = Dungeon(TINY, "tiny")
        state, cost = d.step((1, 2, False), 0, 1)
        self.assertEqual(state, (1, 3, True))
        self.assertEqual(cost, 1)

    def test_admissible_heuristics_never_overestimate(self):
        for d in LEVELS:
            optimal = run_algorithm("UCS", d)
            for mode in ADMISSIBLE:
                d.heuristic_mode = mode
                for i, state in enumerate(optimal.path):
                    remaining = sum(dict(d.successors(a))[b]
                                    for a, b in zip(optimal.path[i:], optimal.path[i + 1:]))
                    self.assertLessEqual(d.heuristic(state), remaining + 1e-9, f"{mode} on {d.name}")
            d.heuristic_mode = "manhattan"

    def test_astar_is_optimal_with_every_admissible_heuristic(self):
        for d in LEVELS:
            best = run_algorithm("UCS", d).cost
            for mode in ADMISSIBLE:
                self.assertEqual(run_algorithm("A*", d, heuristic=mode).cost, best, f"{mode} on {d.name}")

    def test_better_heuristic_expands_fewer_nodes(self):
        d = next(lv for lv in LEVELS if lv.name == "Twin Bridges")
        exp = {m: run_algorithm("A*", d, heuristic=m).expanded for m in ("manhattan", "chebyshev", "zero")}
        self.assertLess(exp["manhattan"], exp["chebyshev"])
        self.assertLess(exp["chebyshev"], exp["zero"])

    def test_weighted_heuristic_still_solves(self):
        for d in LEVELS:
            res = run_algorithm("A*", d, heuristic="weighted")
            self.assertEqual(res.status, SUCCESS)
            validate_path(self, d, res)

    def test_run_algorithm_restores_dungeon_settings(self):
        d = LEVELS[1]
        run_algorithm("A*", d, heuristic="zero", start=(1, 2, False))
        self.assertEqual(d.heuristic_mode, "manhattan")
        self.assertIsNone(d.override_start)

    def test_search_from_a_mid_game_state(self):
        d = LEVELS[1]
        full = run_algorithm("A*", d)
        mid = full.path[len(full.path) // 2]
        rest = run_algorithm("A*", d, start=mid)
        self.assertEqual(rest.path[0], mid)
        self.assertTrue(d.is_goal(rest.path[-1]))
        self.assertLessEqual(rest.cost, full.cost)

    def test_frontier_data_is_consistent(self):
        for d in LEVELS:
            for name in ALGORITHM_ORDER:
                res = run_algorithm(name, d, depth_limit=200)
                self.assertEqual(len(res.explored), len(res.generated))
                self.assertEqual(len(res.explored), len(res.frontier_sizes))
                self.assertEqual(res.frontier_sizes,
                                 frontier_profile(d.start_state, res.explored, res.generated))
                self.assertGreater(res.max_frontier, 0)

    def test_map_editor_painting(self):
        d = Dungeon(TINY, "tiny").clone("copy")
        self.assertEqual(d.paint(1, 4, "mud")[0], [(1, 4)])
        self.assertEqual(d.terrain[1][4], "~")
        changed, msg = d.paint(1, 1, "wall")                 # start cell is protected
        self.assertEqual(changed, [])
        self.assertIn("start", msg)
        changed, _ = d.paint(3, 1, "key")                    # moving the key
        self.assertEqual(d.key, (3, 1))
        self.assertEqual(len(changed), 2)
        self.assertEqual(d.paint(3, 1, "goal")[0], [])       # cannot stack markers

    def test_editing_a_clone_never_changes_the_original(self):
        original = LEVELS[0]
        before = [row[:] for row in original.terrain]
        twin = original.clone()
        twin.paint(1, 2, "water")
        twin.paint(5, 5, "start")
        self.assertEqual(original.terrain, before)
        self.assertEqual(original.start, (1, 1))

    def test_blocked_edit_makes_map_unsolvable(self):
        d = Dungeon(TINY, "tiny").clone()
        self.assertTrue(is_solvable(d))
        d.paint(3, 3, "wall")
        d.paint(2, 5, "wall")
        self.assertFalse(is_solvable(d))

    def test_random_dungeons_are_always_solvable(self):
        for seed in range(40):
            d = random_dungeon(seed=seed)
            self.assertTrue(is_solvable(d), f"seed {seed}")
            res = run_algorithm("A*", d)
            self.assertEqual(res.status, SUCCESS)
            validate_path(self, d, res)

    def test_result_metrics_are_populated(self):
        res = run_algorithm("A*", LEVELS[0])
        self.assertGreater(res.expanded, 0)
        self.assertGreater(res.time_ms, 0)
        self.assertEqual(res.length, len(res.path) - 1)
        self.assertGreaterEqual(len(res.explored), 1)


if __name__ == "__main__":
    unittest.main()
