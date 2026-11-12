"""Benchmark mode - pure logic (no pygame).

Runs every algorithm on N random dungeons (seeds base, base+1, ...) and
averages the metrics, so conclusions don't depend on one lucky map.
"""
import csv
import os
from time import perf_counter
from typing import Dict, List, Optional

from .dungeon import random_dungeon
from .search import ALGORITHM_ORDER, run_algorithm

COUNT_CHOICES = [10, 25, 50, 100]


class Benchmark:
    def __init__(self, count: int = 50, seed: int = 1000, depth_limit: int = 40,
                 heuristic: str = "manhattan", width: int = 25, height: int = 17):
        self.count = count
        self.seed = seed
        self.depth_limit = depth_limit
        self.heuristic = heuristic
        self.width, self.height = width, height
        self.maps_done = 0
        self.records: List[dict] = []
        self.elapsed = 0.0

    # ------------------------------------------------------------ running
    @property
    def done(self) -> bool:
        return self.maps_done >= self.count

    @property
    def progress(self) -> float:
        return self.maps_done / self.count if self.count else 1.0

    def step(self) -> None:
        """Generate the next random map and run all seven algorithms on it."""
        if self.done:
            return
        t0 = perf_counter()
        map_seed = self.seed + self.maps_done
        dungeon = random_dungeon(self.width, self.height, seed=map_seed)
        results = {name: run_algorithm(name, dungeon, self.depth_limit, heuristic=self.heuristic)
                   for name in ALGORITHM_ORDER}
        optimal = results["UCS"].cost            # UCS is optimal and always solves these maps
        for name, res in results.items():
            self.records.append({
                "map": self.maps_done + 1, "seed": map_seed, "algorithm": name,
                "status": res.status, "solved": res.found,
                "length": res.length, "cost": res.cost, "optimal_cost": optimal,
                "expanded": res.expanded, "frontier": res.max_frontier, "time_ms": res.time_ms,
            })
        self.maps_done += 1
        self.elapsed += perf_counter() - t0

    def run_all(self) -> None:
        while not self.done:
            self.step()

    # ---------------------------------------------------------- summaries
    def summary(self) -> Dict[str, dict]:
        out: Dict[str, dict] = {}
        for name in ALGORITHM_ORDER:
            rows = [r for r in self.records if r["algorithm"] == name]
            solved = [r for r in rows if r["solved"]]

            def avg(key, pool):
                return sum(r[key] for r in pool) / len(pool) if pool else None

            out[name] = {
                "maps": len(rows),
                "solved_pct": 100.0 * len(solved) / len(rows) if rows else 0.0,
                "optimal_pct": (100.0 * sum(1 for r in solved if r["cost"] <= r["optimal_cost"] + 1e-9)
                                / len(rows)) if rows else 0.0,
                "avg_cost": avg("cost", solved),
                "cost_ratio": (sum(r["cost"] / r["optimal_cost"] for r in solved) / len(solved))
                if solved else None,
                "avg_length": avg("length", solved),
                "avg_expanded": avg("expanded", rows),
                "avg_frontier": avg("frontier", rows),
                "avg_time_ms": avg("time_ms", rows),
            }
        return out

    def insights(self) -> List[str]:
        """A few plain-English conclusions generated from the measured data."""
        s = self.summary()
        if not self.records:
            return []
        lines = []
        optimal = [n for n in ALGORITHM_ORDER if s[n]["optimal_pct"] >= 99.99]
        lines.append("Lowest-cost path on every map: " + (", ".join(optimal) if optimal else "none") + ".")

        u, a = s["UCS"]["avg_expanded"], s["A*"]["avg_expanded"]
        if u and a is not None:
            pct = (1 - a / u) * 100
            word = "fewer" if pct >= 0 else "more"
            lines.append(f"A* expanded {abs(pct):.0f}% {word} nodes than UCS while finding the same optimal cost.")

        g = s["Greedy"]
        if g["avg_expanded"] is not None and a:
            lines.append(f"Greedy expanded {100 * g['avg_expanded'] / a:.0f}% as many nodes as A*, but its paths "
                         f"cost {g['cost_ratio']:.2f}x the optimum on average.")

        b = s["BFS"]
        if b["cost_ratio"] is not None:
            lines.append(f"BFS minimises steps, not cost: its paths cost {b['cost_ratio']:.2f}x the optimum on average.")

        d = s["DLS"]
        lines.append(f"DLS (limit {self.depth_limit}) solved {d['solved_pct']:.0f}% of the maps; "
                     f"IDS expanded {s['IDS']['avg_expanded'] / max(a or 1, 1):.0f}x more nodes than A*.")
        return lines

    # ------------------------------------------------------------- export
    def save_csv(self, directory: str) -> List[str]:
        os.makedirs(directory, exist_ok=True)
        summary_path = os.path.join(directory, f"benchmark_summary_{self.count}maps.csv")
        runs_path = os.path.join(directory, f"benchmark_runs_{self.count}maps.csv")
        with open(summary_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["algorithm", "maps", "solved_pct", "optimal_pct", "avg_cost", "cost_vs_optimal",
                        "avg_steps", "avg_expanded", "avg_peak_frontier", "avg_time_ms"])
            for name, m in self.summary().items():
                def f(v, nd=2):
                    return "" if v is None else f"{v:.{nd}f}"
                w.writerow([name, m["maps"], f(m["solved_pct"], 1), f(m["optimal_pct"], 1), f(m["avg_cost"]),
                            f(m["cost_ratio"], 3), f(m["avg_length"]), f(m["avg_expanded"], 1),
                            f(m["avg_frontier"], 1), f(m["avg_time_ms"], 3)])
        with open(runs_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["map", "seed", "algorithm", "status", "steps", "cost", "optimal_cost",
                        "expanded", "peak_frontier", "time_ms"])
            for r in self.records:
                w.writerow([r["map"], r["seed"], r["algorithm"], r["status"], r["length"], f"{r['cost']:g}",
                            f"{r['optimal_cost']:g}", r["expanded"], r["frontier"], f"{r['time_ms']:.3f}"])
        return [summary_path, runs_path]
