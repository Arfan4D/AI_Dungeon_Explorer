# AI Dungeon Explorer: The Lost Temple

**CSE 366 — Artificial Intelligence · Group 07**
Momin Khair Arfan (2023-2-60-041) · Sakibull Hasan Sakib (2023-2-60-039) · Farhana Forhad Mim (2023-2-60-276)

A 2D dungeon game built with **Python + Pygame** that shows how AI search algorithms solve a
path-finding problem. The explorer must **collect the key**, then reach the **locked treasure chamber**,
while walls block the way and mud / water make some cells more expensive.

Watch the seven algorithms explore the dungeon, **race them side by side**, **inspect their queues cell by cell**,
**benchmark them on 100 random maps**, edit the map yourself, or play manually.

---

## 1. Run it

### Option A — double-click (Windows)
Double-click **`run_game.bat`**. The first run creates a virtual environment and installs Pygame automatically.

### Option B — VS Code
1. Install **Python 3.10 – 3.13** (python.org). Pygame installs most reliably on these versions.
2. `File > Open Folder...` and choose the folder that **directly contains `main.py`**.
3. In the terminal (`` Ctrl+` ``):

   ```bash
   # Windows (Git Bash)                      # Windows (cmd/PowerShell)          # macOS / Linux
   py -3.12 -m venv .venv                    py -3.12 -m venv .venv              python3 -m venv .venv
   source .venv/Scripts/activate             .venv\Scripts\activate              source .venv/bin/activate

   pip install -r requirements.txt
   python main.py
   ```
4. Tests (no display needed): `python -m unittest discover tests -v` (46 tests)

### Option C — a single `.exe` (no Python needed on the lab PC)
**Build it once, then copy the file anywhere:**

| Way | How |
|---|---|
| **On your PC** | Double-click **`build_exe.bat`**. After about a minute you get `dist\AI_Dungeon_Explorer.exe`. |
| **In the cloud** | Push the project to GitHub → *Actions* → **Build Windows exe** → *Run workflow* → download the artifact. |
| macOS / Linux | `bash build_exe.sh` |

The script creates its own environment, installs Pygame + PyInstaller, runs the unit tests, then builds a
windowed one-file executable with the project icon. Results (`results/`) and screenshots (`screenshots/`) are saved
**next to the .exe**.

If the build fails or Windows Defender complains: re-run the command in `build_exe.bat` without `--noconsole`
to see errors, and click *More info → Run anyway* if SmartScreen warns about an unsigned app (normal for student projects).

---

## 2. Feature tour

| Feature | What it shows |
|---|---|
| **7 algorithms** | BFS, DFS, UCS, DLS, IDS, Greedy Best-First, A* |
| **Algorithm Race** (`V`) | 2–4 algorithms solve the **same map at the same time**, side by side, with a live leaderboard and a combined frontier-size chart |
| **Cell inspector + queue panel** (`I`) | Hover any cell for its **g, h, f values and parent**; the queue panel shows the next nodes to be expanded, sorted by the algorithm's own rule |
| **Benchmark mode** (`B`) | Runs all algorithms on 10–100 random dungeons and averages cost, optimality, expansions, frontier, time — with auto-written conclusions and CSV export |
| **Step mode** | Press `F` to expand **one node at a time**; `P` pauses |
| **Frontier overlay + chart** | Orange = waiting in the frontier, blue = explored, purple = explored while carrying the key |
| **5 heuristics** (`H`) | Manhattan, Euclidean, Chebyshev, Zero, and an *inadmissible* Manhattan×3 |
| **Comparison dashboard** (`C`) | Algorithms page + heuristic-study page, switchable bar charts, CSV export |
| **Map editor** (`E`) | Paint walls / mud / water, move start, key, treasure — then run any algorithm |
| **Manual play** (`M`) | Hint (A* route), undo, 1–3 star rating |
| **Random dungeons** (`N`) | Always solvable |
| **5 hand-made levels**, title screen, sound, effects, screenshots (`F12`) | Presentation polish |

Press **F1** in the game for the full list of controls.

## 3. Controls

| Action | Key |
|---|---|
| Choose algorithm | `1`–`7` or click (BFS, DFS, UCS, DLS, IDS, Greedy, A*) |
| Run / Reset | `Space` or `Enter` / `R` |
| Pause–resume / Step one node | `P` / `F` |
| **Inspector (queue panel + hover info)** | `I` |
| **Algorithm Race** | `V` |
| **Benchmark** | `B` |
| Heuristic (Greedy & A*) | `H` |
| DLS depth limit −5 / +5 | `-` / `=` |
| Animation speed slower / faster | `,` / `.` |
| AI Solver ⇄ Manual play | `M` |
| Move / Undo / Hint (manual) | Arrows or `WASD` / `Backspace` or `Z` / `T` |
| Previous / next level, random map | `[` `]` / `N` |
| Map editor (brushes `1`–`7`) | `E` — left-drag paints, right-click erases |
| Dashboard (Tab = bars, ←/→ = page, S = CSV) | `C` |
| Sound, help, screenshot, quit | `X`, `F1`, `F12`, `Esc` |

**Inside Race mode:** `1`–`7` toggle algorithms (2–4), `Space` start/restart, `P` pause, `K` skip to the end,
`,` `.` speed, `[` `]` change level, `N` random map, `Esc` back.
**Inside Benchmark mode:** `Space` re-run, `N` new seeds, `Tab` change bars, `S` save CSV, `Esc` back.

## 4. How the problem is modelled

| Element | Definition |
|---|---|
| **State** | `(row, col, has_key)` |
| **Actions** | Up, Right, Down, Left |
| **Transition** | Entering a non-wall cell; entering the key cell sets `has_key = True` |
| **Step cost** | Floor `1`, Mud `3`, Water `5` (cost of the cell being entered) |
| **Goal test** | Standing on the treasure cell — it can only be entered when `has_key` is true |
| **Heuristic** | Key-aware: `d(pos,key) + d(key,goal)` before the key, `d(pos,goal)` after. `d` is Manhattan / Euclidean / Chebyshev / 0 (all admissible because every step costs ≥ 1) or 3×Manhattan (deliberately inadmissible). |

## 5. Algorithms (`game/search.py`)

| Algorithm | Data structure | Selection rule | Fewest steps | Lowest cost |
|---|---|---|---|---|
| BFS | FIFO queue + reached set | shallowest node | yes | no |
| DFS | LIFO stack + visited set | deepest node | no | no |
| UCS | priority queue | lowest `g(n)` | no | **yes** |
| DLS | LIFO stack | DFS, never deeper than limit `L` | no | no |
| IDS | repeated DLS | limit 0, 1, 2, … | yes | no |
| Greedy Best-First | priority queue | lowest `h(n)` | no | no |
| A* | priority queue | lowest `g(n)+h(n)` | no | **yes** (admissible `h`) |

* The goal test happens when a node is **expanded**, for every algorithm, so *expanded nodes* is comparable.
* **DLS** reports **"Depth limit reached"** separately from **"No path found"**.
* **IDS** counts the expanded nodes of *all* iterations; the animation, race and frontier chart replay only the last pass.
* Every run records **each expansion's g-value, parent and generated children** — that trace powers the step mode,
  the frontier overlay, the inspector and the race.

---

## 6. The three new tools

### Algorithm Race (`V`)
Pick 2–4 algorithms and press **Start Race**. They all solve the same dungeon on a shared clock:
* while exploring, **1 tick = 1 node expansion**, so an algorithm that does less work finishes sooner;
* walking the final path costs **5 ticks per step**, so a long path costs time too.

You see the maps side by side, each lane's explored area and frontier, a live leaderboard (expanded nodes, cost, steps,
peak frontier, race time) and a combined **frontier-size chart**. The result line names *who reached the treasure first*
and *who found the cheapest path* — these are often different algorithms, which is the whole lesson.

### Cell inspector + queue panel (`I`)
* **Hover** any cell: terrain, and — if the search has touched it — *expanded #N*, **g, h, f** and its **parent**
  (separately for "no key" and "with key", since the key is part of the state), or its g/h/f while waiting in the frontier.
* **Queue panel** (top-right of the map): the data structure type (FIFO queue / LIFO stack / priority queue), the node
  just expanded, and the next 7 nodes **in the exact order the algorithm will take them** — by age (BFS), recency
  (DFS/DLS/IDS), `g` (UCS), `h` (Greedy) or `f = g + h` (A*).
* Combine with **Step (`F`)** to walk an audience through one expansion at a time.

### Benchmark mode (`B`)
Runs every algorithm on **N random dungeons** (seeds are shown, so results are reproducible) and averages the metrics.
Optimality is measured against the UCS cost on each map. It writes conclusions from the measured data and exports
`results/benchmark_summary_*.csv` and `results/benchmark_runs_*.csv`.

**Verified result — 50 maps, seeds 1000–1049, DLS limit 40, Manhattan heuristic:**

| Algorithm | Solved | Optimal | Avg cost | vs optimal | Avg steps | Avg expanded | Avg peak frontier |
|---|---|---|---|---|---|---|---|
| BFS | 100% | 46% | 70.9 | 1.07× | 49.6 | 328 | 17.2 |
| DFS | 100% | 0% | 173.9 | 2.83× | 128.1 | 181 | 25.6 |
| UCS | 100% | **100%** | 66.3 | 1.00× | 51.0 | 327 | 18.4 |
| DLS | 20% | 2% | 56.4 | 1.19× | 39.4 | 685 | 12.7 |
| IDS | 100% | 46% | 70.9 | 1.07× | 49.6 | 16813 | 15.0 |
| Greedy | 100% | 20% | 76.0 | 1.15× | 53.4 | **66** | 18.7 |
| A* | 100% | **100%** | 66.3 | 1.00× | 51.1 | 168 | 18.2 |

*(Cost and steps are averaged over solved maps only.)* Conclusions: UCS and A* are optimal on every map; **A\*
expands 49% fewer nodes than UCS**; Greedy is cheapest in work but pays **1.15×** the optimal cost; BFS minimises steps,
not cost (1.07×); IDS repeats work (~100× A*'s expansions); DLS with limit 40 only solves 20% of the larger random maps.

---

## 7. Suggested demo script (≈ 7 minutes)

1. **Title screen → Enter.** State the problem model: state `(row, col, has_key)`, actions, step costs.
2. **Race (`V`):** keep BFS, UCS, A* on *Twin Bridges* → **Start**. A* reaches the treasure first (≈ 5 s race time vs ≈ 19–20 s);
   point at the explored areas and the frontier chart. Note UCS and A* find the same **cheapest** path while BFS pays 54 vs 36.
3. **Esc → pick A\* → `I` (inspector) → `F` a few times.** Hover cells: show g, h, f and the parent. Show the
   queue panel sorted by f. Press `1` for BFS: the same panel is now a FIFO queue; press `2` for DFS: it becomes a LIFO stack.
4. **`H`** to change the heuristic and re-run A*: Manhattan 37 → Euclidean 132 → Chebyshev 169 → Zero 574 expansions.
5. **Benchmark (`B`):** 50 maps run in ~3 seconds. Read the "What the data says" box; press `Tab` for the cost / frontier bars; `S` to export.
6. **Editor (`E`):** wall off the treasure → *No path found*. Lower the DLS limit with `-` → *Depth limit reached*.
7. **Manual play (`M`):** `T` for a hint; finish the level and show the star rating.

## 8. Viva cheat-sheet

* **Why is A\* optimal here?** The heuristic never over-estimates the remaining cost (each step costs ≥ 1 and
  Manhattan ≤ steps), so it is *admissible*. Manhattan×3 breaks this — try it with `H`.
* **Why doesn't BFS find the cheapest path?** BFS minimises the *number of steps*; it treats mud (3) and water (5)
  like floor (1). UCS and A* use path cost `g(n)`.
* **What do g, h and f mean?** `g` = cost so far, `h` = estimated cost to go, `f = g + h` = estimated total through that node
  (hover any cell with the inspector).
* **Why does Greedy expand few nodes but return worse paths?** It follows `h(n)` only and ignores the cost so far.
* **Why is IDS so expensive?** It re-runs DLS for every limit, so shallow nodes are expanded many times — but its memory stays small.
* **What is the "peak frontier"?** The largest number of generated-but-unexpanded states: a measure of memory.
* **Why is the key part of the state?** Without it the chamber lock could not be modelled; the same cell means
  different things with and without the key.
* **DLS vs "no path"?** DLS can fail only because of its cut-off, so it reports a different status than a true exhaustive failure.
* **Why a benchmark over many maps?** One map can be lucky; averaging over 50–100 seeded random dungeons gives evidence.

## 9. Project structure

```
AI_Dungeon_Explorer/
├── main.py               entry point
├── requirements.txt      pygame
├── run_game.bat          double-click launcher (Windows)
├── build_exe.bat/.sh     build a single-file executable
├── assets/icon.ico       app icon (generated by tools/make_icon.py)
├── tools/make_icon.py    regenerates the icon (pure Python)
├── .github/workflows/    build-exe.yml  (cloud build of the Windows .exe)
├── game/
│   ├── settings.py       window layout, colours, terrain costs, team info
│   ├── paths.py          data folder (works inside a packaged .exe)
│   ├── dungeon.py        grid + problem model + heuristics + editor + random generator
│   ├── levels.py         5 hand-crafted dungeons (ASCII maps)
│   ├── search.py         BFS, DFS, UCS, DLS, IDS, Greedy, A* (+ full expansion trace)
│   ├── race.py           Algorithm Race logic (pure Python)
│   ├── benchmark.py      Benchmark logic + insights + CSV (pure Python)
│   ├── screens.py        Race and Benchmark screens
│   ├── ui.py             buttons, text helpers, two-page comparison dashboard
│   ├── graphics.py       procedural sprites + particle effects
│   ├── sound.py          synthesised sound effects
│   └── game.py           game loop, animation, manual mode, editor, inspector, rendering
├── tests/                46 unit tests (algorithms, heuristics, editor, race, benchmark, trace)
├── results/              CSV exports
└── screenshots/          F12 screenshots
```

## 10. The five levels

| Level | Designed to show |
|---|---|
| Entrance Hall | A long maze — DLS needs limit ≥ 135; IDS repeats a lot of work |
| Mud Flats | BFS pays 74, UCS/A* pay 40; DFS wanders 320 steps; A* beats UCS 127 vs 505 expansions |
| Twin Bridges | Cheap floor bridge vs mud bridge vs water — A* needs only 37 expansions; ideal for the race and heuristic study |
| Dead-End Pocket | A U-shaped trap in front of the treasure; Greedy returns a worse path than A* |
| Labyrinth of Echoes | Maze with loops — all algorithms close; good for step mode and the inspector |

Add your own in `game/levels.py` (`#` wall, `.` floor, `~` mud, `w` water, `S` start, `K` key, `T` treasure) or use the in-game editor.

## 11. Proposal checklist

| Proposal item | Where |
|---|---|
| 5 uninformed + 2 informed algorithms | `game/search.py` |
| Dungeon as state-space graph with obstacles, terrain costs, key, goal | `game/dungeon.py`, `game/levels.py` |
| Visualise explored states and final path | `game/game.py` (frontier overlay, inspector) |
| Compare length / cost / expanded / time | dashboard (`C`), Race (`V`), Benchmark (`B`), CSV export |
| Manual mode and AI mode | `M` key / mode button |
| Algorithm selection menu, animated search | side panel, speed / pause / step controls |
| Weighted terrain and blocked cells | mud, water, walls, map editor |
| Key collection and locked-goal mechanics | `Dungeon.step()` |
| Success / failure / depth-limit messages | status bar, result banner, stats box |
| Algorithms tested independently of the game | `tests/` |
