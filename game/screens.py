"""Full-window screens: Algorithm Race and Benchmark."""
from time import perf_counter

import pygame

from . import settings as S
from .benchmark import COUNT_CHOICES, Benchmark
from .dungeon import HEURISTIC_LABELS, random_dungeon
from .graphics import draw_chest, draw_explorer, draw_key
from .levels import LEVELS
from .race import MAX_RACERS, MIN_RACERS, Race
from .search import ALGORITHM_ORDER, FULL_NAMES
from .ui import Button, draw_text, wrap_text

COL = S.COLORS

# One identity colour per race lane (used for the header text and the chart lines).
LANE_COLORS = [(255, 150, 60), (90, 200, 255), (150, 255, 160), (220, 150, 255)]


# ====================================================================
#  Algorithm Race
# ====================================================================
class RaceScreen:
    HEADER_H = 28

    def __init__(self, fonts, sound, render_map):
        self.fonts = fonts
        self.sound = sound
        self.render_map = render_map          # callable(dungeon, cell_size) -> Surface
        self.names = ["BFS", "UCS", "A*"]
        self.race = None
        self.speed_index = 3
        self.dungeon = LEVELS[0]
        self.level_index = 0
        self.depth_limit = S.DEFAULT_DEPTH_LIMIT
        self.heuristic = "manhattan"
        self.message = ""
        self._cache_key = None
        self.map_surface = None
        self.overlays = {}
        self.panels = []
        self.chart_rect = None
        self.cs = 12

        self.toggle_buttons = {}
        for i, name in enumerate(ALGORITHM_ORDER):
            self.toggle_buttons[name] = Button((16 + i * 104, 8, 98, 30), name,
                                               lambda n=name: self.toggle_algo(n))
        self.start_button = Button((16, 46, 150, 30), "Start Race (Space)", self.start)
        self.pause_button = Button((174, 46, 100, 30), "Pause (P)", self.toggle_pause)
        self.skip_button = Button((282, 46, 100, 30), "Skip (K)", self.skip)
        self.speed_minus = Button((390, 46, 30, 30), "-", lambda: self.change_speed(-1))
        self.speed_plus = Button((486, 46, 30, 30), "+", lambda: self.change_speed(1))
        self.prev_button = Button((528, 46, 34, 30), "<", lambda: self.change_level(-1))
        self.next_button = Button((570, 46, 34, 30), ">", lambda: self.change_level(1))
        self.random_button = Button((612, 46, 120, 30), "Random (N)", self.random_map)
        self.back_button = Button((S.WINDOW_W - 116, 46, 100, 30), "Back (Esc)", lambda: setattr(self, "_back", True))
        self._back = False
        self.buttons = (list(self.toggle_buttons.values()) + [
            self.start_button, self.pause_button, self.skip_button, self.speed_minus, self.speed_plus,
            self.prev_button, self.next_button, self.random_button, self.back_button])

    # -------------------------------------------------------------- setup
    def open(self, dungeon, depth_limit, heuristic):
        self.dungeon = dungeon
        self.depth_limit = depth_limit
        self.heuristic = heuristic
        self.race = None
        self._back = False
        self.message = ("Pick 2-4 algorithms, then press Start Race. All of them solve the same dungeon "
                        "at once; the clock counts node expansions, so less work = faster.")

    def toggle_algo(self, name):
        if name in self.names:
            if len(self.names) <= MIN_RACERS:
                self.message = f"A race needs at least {MIN_RACERS} algorithms."
                return
            self.names.remove(name)
        else:
            if len(self.names) >= MAX_RACERS:
                self.message = f"At most {MAX_RACERS} algorithms can race at once."
                return
            self.names.append(name)
            self.names.sort(key=ALGORITHM_ORDER.index)
        self.race = None

    def start(self):
        self.race = Race(self.dungeon, self.names, self.depth_limit, self.heuristic)
        self.message = "Racing! The clock counts node expansions; walking a path costs time too."

    def toggle_pause(self):
        if self.race and not self.race.done:
            self.race.paused = not self.race.paused

    def skip(self):
        if self.race:
            self.race.jump_to_end()
            self._announce_done()

    def change_speed(self, delta):
        self.speed_index = max(0, min(len(S.SPEED_STEPS) - 1, self.speed_index + delta))

    def change_level(self, step):
        self.level_index = (self.level_index + step) % len(LEVELS)
        self.dungeon = LEVELS[self.level_index]
        self.race = None

    def random_map(self):
        import random
        self.dungeon = random_dungeon(seed=random.randint(1, 9999))
        self.race = None

    # ------------------------------------------------------------- events
    def handle_event(self, event):
        """Returns 'back' when the player leaves the race screen."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            for b in self.buttons:
                if b.handle(event):
                    self.sound.play("click")
                    break
        elif event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self._back = True
            elif k in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
            elif k == pygame.K_p:
                self.toggle_pause()
            elif k == pygame.K_k:
                self.skip()
            elif k == pygame.K_PERIOD:
                self.change_speed(1)
            elif k == pygame.K_COMMA:
                self.change_speed(-1)
            elif k == pygame.K_LEFTBRACKET:
                self.change_level(-1)
            elif k == pygame.K_RIGHTBRACKET:
                self.change_level(1)
            elif k == pygame.K_n:
                self.random_map()
            elif pygame.K_1 <= k <= pygame.K_7:
                self.toggle_algo(ALGORITHM_ORDER[k - pygame.K_1])
        if self._back:
            self._back = False
            return "back"
        return None

    def _announce_done(self):
        if self.race and self.race.done:
            w = ", ".join(r.name for r in self.race.winners())
            c = self.race.cheapest()
            cheap = ", ".join(r.name for r in c)
            self.message = (f"Race finished! First to the treasure: {w}.  "
                            f"Cheapest path: {cheap} (cost {self.race.best_cost:g})." if c else
                            "Race finished - nobody reached the treasure.")

    def update(self, dt):
        if not self.race:
            return
        was_done = self.race.done
        for r in self.race.update(min(dt, 0.05), S.SPEED_STEPS[self.speed_index]):
            if not r.result.found:
                self.sound.play("fail")
            elif r.rank == 1:
                self.sound.play("win")
            else:
                self.sound.play("key")
        if self.race.done and not was_done:
            self._announce_done()

    # ------------------------------------------------------------- layout
    def _layout(self):
        n = len(self.names)
        d = self.dungeon
        area = pygame.Rect(16, 88, S.WINDOW_W - 32, 548)
        cols, rows = {2: (2, 1), 3: (3, 1), 4: (2, 2)}[n]
        gap = 8 if rows == 1 else 6
        pw = (area.w - gap * (cols - 1)) // cols
        ph = (area.h - gap * (rows - 1)) // rows
        cs = max(6, min(pw // d.width, (ph - self.HEADER_H - 4) // d.height))
        self.panels = []
        for i in range(n):
            r, c = divmod(i, cols)
            self.panels.append(pygame.Rect(area.x + c * (pw + gap), area.y + r * (ph + gap),
                                           pw, self.HEADER_H + d.height * cs + 4))
        self.chart_rect = None
        if rows == 1:
            top = self.panels[0].bottom + 8
            if area.bottom - top >= 90:
                self.chart_rect = pygame.Rect(area.x, top, area.w, area.bottom - top)
        key = (id(d), cs)
        if key != self._cache_key:
            self._cache_key = key
            self.cs = cs
            self.map_surface = self.render_map(d, cs)
            self.overlays = {}
            for name, color, alpha in (("explored", COL["explored"], 120), ("explored_key", COL["explored_key"], 120),
                                       ("frontier", COL["frontier"], 185)):
                surf = pygame.Surface((cs, cs), pygame.SRCALPHA)
                surf.fill((*color, alpha))
                self.overlays[name] = surf

    # ------------------------------------------------------------ drawing
    def _refresh_buttons(self):
        for name, b in self.toggle_buttons.items():
            b.selected = name in self.names
        racing = self.race is not None and not self.race.done
        self.start_button.label = "Restart (Space)" if self.race else "Start Race (Space)"
        self.pause_button.enabled = racing
        self.pause_button.label = "Resume (P)" if (self.race and self.race.paused) else "Pause (P)"
        self.pause_button.selected = bool(self.race and self.race.paused and racing)
        self.skip_button.enabled = racing

    def draw(self, surf, t):
        self._layout()
        self._refresh_buttons()
        small, tiny = self.fonts["small"], self.fonts["tiny"]
        surf.fill(COL["bg"])

        for b in self.buttons:
            b.draw(surf, small)
        draw_text(surf, f"Speed x{S.SPEED_STEPS[self.speed_index]:g}", small, COL["text"], (453, 61), "center")
        lbl = self.dungeon.name if self.dungeon not in LEVELS else \
            f"Level {self.level_index + 1}/{len(LEVELS)}: {self.dungeon.name}"
        draw_text(surf, lbl, small, COL["accent"], (744, 61), "midleft")
        draw_text(surf, "ALGORITHM RACE", tiny, COL["info"], (S.WINDOW_W - 16, 12), "topright")
        info = f"DLS limit {self.depth_limit}  |  heuristic {HEURISTIC_LABELS[self.heuristic]}"
        draw_text(surf, info, tiny, COL["muted"], (S.WINDOW_W - 16, 28), "topright")

        d, cs = self.dungeon, self.cs
        for i, rect in enumerate(self.panels):
            racer = self.race.racers[i] if self.race else None
            self._draw_panel(surf, rect, self.names[i], racer, LANE_COLORS[i], t)

        if self.chart_rect:
            self._draw_chart(surf, self.chart_rect)
        self._draw_leaderboard(surf)

    def _draw_panel(self, surf, rect, name, racer, lane_color, t):
        d, cs = self.dungeon, self.cs
        small, tiny = self.fonts["small"], self.fonts["tiny"]
        border = COL["panel_edge"]
        if racer and racer.finished and racer.rank == 1:
            border = COL["accent"]
        pygame.draw.rect(surf, COL["panel"], rect, border_radius=8)
        pygame.draw.rect(surf, border, rect, 3 if border == COL["accent"] else 1, border_radius=8)
        draw_text(surf, FULL_NAMES[name], small, lane_color, (rect.x + 10, rect.y + 5))

        # right side of the header: live status
        if racer is None:
            status, color = "ready", COL["muted"]
        elif racer.phase == "exploring":
            status, color = f"expanded {racer.expanded_count}", COL["text"]
        elif racer.phase == "walking":
            status, color = "walking to the treasure", COL["path"]
        elif not racer.result.found:
            status, color = ("NO PATH" if racer.result.status == "failure" else "DEPTH LIMIT"), COL["bad"]
        else:
            status, color = f"FINISHED #{racer.rank}", COL["accent"] if racer.rank == 1 else COL["good"]
        draw_text(surf, status, small, color, (rect.right - 10, rect.y + 5), "topright")

        ox = rect.x + (rect.w - d.width * cs) // 2
        oy = rect.y + self.HEADER_H
        surf.blit(self.map_surface, (ox, oy))

        def cell(r, c):
            return pygame.Rect(ox + c * cs, oy + r * cs, cs, cs)

        state = d.start_state
        if racer is not None:
            res = racer.result
            racer.sync_frontier()
            if racer.phase == "exploring":
                for r, c, _k in racer.frontier:
                    surf.blit(self.overlays["frontier"], cell(r, c).topleft)
            shown = racer.shown
            for r, c, k in res.explored[:shown]:
                surf.blit(self.overlays["explored_key" if k else "explored"], cell(r, c).topleft)
            if racer.phase == "exploring" and shown > 0:
                r, c, _k = res.explored[shown - 1]
                pygame.draw.rect(surf, (255, 255, 255), cell(r, c), 1)

        pygame.draw.circle(surf, COL["start"], cell(*d.start).center, max(3, int(cs * 0.42)), 1)

        pos = cell(d.start[0], d.start[1]).center
        has_key = False
        moving = False
        if racer is not None and racer.result.found and racer.phase in ("walking", "finished"):
            path = racer.result.path
            idx = racer.walk_index
            i = min(int(idx), len(path) - 1)
            j = min(i + 1, len(path) - 1)
            a, b = cell(path[i][0], path[i][1]).center, cell(path[j][0], path[j][1]).center
            f = idx - i
            pos = (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f))
            has_key = path[i][2]
            moving = racer.phase == "walking"
            pts = [cell(p[0], p[1]).center for p in path[:i + 1]] + [pos]
            if len(pts) >= 2:
                pygame.draw.lines(surf, COL["path"], False, pts, max(2, cs // 5))

        if not has_key:
            draw_key(surf, cell(*d.key).center, cs, t)
        draw_chest(surf, cell(*d.goal), has_key, t)
        draw_explorer(surf, pos, cs, has_key, t, moving)

    def _draw_chart(self, surf, rect):
        small, tiny = self.fonts["small"], self.fonts["tiny"]
        pygame.draw.rect(surf, COL["panel"], rect, border_radius=8)
        pygame.draw.rect(surf, COL["panel_edge"], rect, 1, border_radius=8)
        draw_text(surf, "Frontier size over race time (memory use)", small, COL["info"], (rect.x + 12, rect.y + 6))
        inner = pygame.Rect(rect.x + 44, rect.y + 32, rect.w - 64, rect.h - 48)
        pygame.draw.line(surf, COL["panel_edge"], (inner.x, inner.bottom), (inner.right, inner.bottom))
        pygame.draw.line(surf, COL["panel_edge"], (inner.x, inner.y), (inner.x, inner.bottom))
        if not self.race:
            draw_text(surf, "Start the race to compare how large each frontier grows.", small, COL["muted"],
                      inner.center, "center")
            return
        race = self.race
        peak = max([max(r.result.frontier_sizes or [1]) for r in race.racers] + [1])
        draw_text(surf, str(peak), tiny, COL["muted"], (inner.x - 6, inner.y), "topright")
        draw_text(surf, "0", tiny, COL["muted"], (inner.x - 6, inner.bottom - 12), "topright")
        for i, r in enumerate(race.racers):
            sizes = r.result.frontier_sizes
            n = len(sizes)
            if n == 0:
                continue
            step = max(1, n // 250)
            pts = []
            for k in range(0, n, step):
                tick = (k + 1) / n * r.total_expand
                if tick > race.ticks:
                    break
                pts.append((inner.x + inner.w * tick / race.max_finish,
                            inner.bottom - inner.h * sizes[k] / peak))
            if len(pts) >= 2:
                pygame.draw.lines(surf, LANE_COLORS[i], False, pts, 2)
            if pts:
                pygame.draw.circle(surf, LANE_COLORS[i], (int(pts[-1][0]), int(pts[-1][1])), 4)
            lx = rect.right - 14 - (len(race.racers) - i) * 92
            pygame.draw.rect(surf, LANE_COLORS[i], (lx, rect.y + 10, 10, 10), border_radius=2)
            draw_text(surf, r.name, tiny, COL["text"], (lx + 15, rect.y + 8))
        x = inner.x + inner.w * race.ticks / race.max_finish
        pygame.draw.line(surf, (110, 104, 134), (x, inner.y), (x, inner.bottom))

    def _draw_leaderboard(self, surf):
        tiny, small = self.fonts["tiny"], self.fonts["small"]
        y0 = 640
        cols = [("Algorithm", 18), ("Status", 200), ("Expanded", 360), ("Cost", 450), ("Steps", 520),
                ("Peak frontier", 590), ("Race time", 700)]
        for title, x in cols:
            draw_text(surf, title, tiny, COL["info"], (x, y0))
        race = self.race
        for i, name in enumerate(self.names):
            y = y0 + 15 + i * 16
            racer = race.racers[i] if race else None
            draw_text(surf, name, small, LANE_COLORS[i], (cols[0][1], y))
            if racer is None:
                draw_text(surf, "ready", small, COL["muted"], (cols[1][1], y))
                continue
            res = racer.result
            if racer.phase == "exploring":
                status, color = f"exploring {int(100 * racer.ticks / racer.total_expand)}%", COL["text"]
            elif racer.phase == "walking":
                status, color = "walking", COL["path"]
            elif not res.found:
                status, color = ("no path" if res.status == "failure" else "depth limit"), COL["bad"]
            else:
                status, color = f"finished #{racer.rank}", COL["accent"] if racer.rank == 1 else COL["good"]
            draw_text(surf, status, small, color, (cols[1][1], y))
            draw_text(surf, racer.expanded_count, small, COL["text"], (cols[2][1], y))
            if racer.phase != "exploring" and res.found:
                best = racer.finished and res.cost == race.best_cost
                draw_text(surf, f"{res.cost:g}", small, COL["good"] if best else COL["text"], (cols[3][1], y))
                draw_text(surf, res.length, small, COL["text"], (cols[4][1], y))
            draw_text(surf, res.max_frontier, small, COL["text"], (cols[5][1], y))
            if racer.finished and res.found:
                draw_text(surf, f"{racer.finish_seconds:.1f} s", small, COL["text"], (cols[6][1], y))
        # summary / message
        msg = self.message
        for i, line in enumerate(wrap_text(msg, small, 380)[:4]):
            draw_text(surf, line, small, COL["accent"] if (race and race.done) else COL["muted"],
                      (S.WINDOW_W - 16, y0 + i * 18), "topright")


# ====================================================================
#  Benchmark
# ====================================================================
class BenchmarkScreen:
    METRICS = [
        ("Avg expanded nodes", "avg_expanded"),
        ("Avg path cost", "avg_cost"),
        ("Cost vs optimal", "cost_ratio"),
        ("Avg peak frontier", "avg_frontier"),
        ("Avg time (ms)", "avg_time_ms"),
    ]
    COLUMNS = [  # title, x, key, format
        ("Algorithm", 24, None, None),
        ("Solved", 150, "solved_pct", "{:.0f}%"),
        ("Optimal", 226, "optimal_pct", "{:.0f}%"),
        ("Avg cost", 304, "avg_cost", "{:.1f}"),
        ("vs optimal", 384, "cost_ratio", "{:.2f}x"),
        ("Avg steps", 472, "avg_length", "{:.1f}"),
        ("Avg expanded", 560, "avg_expanded", "{:.0f}"),
        ("Avg frontier", 676, "avg_frontier", "{:.1f}"),
        ("Avg time ms", 772, "avg_time_ms", "{:.2f}"),
    ]
    BAR_X = 880

    def __init__(self, fonts, sound, results_dir):
        self.fonts, self.sound, self.results_dir = fonts, sound, results_dir
        self.rect = pygame.Rect(16, 12, S.WINDOW_W - 32, S.WINDOW_H - 24)
        self.bench = None
        self.count = 50
        self.seed = 1000
        self.metric = 0
        self.depth_limit = S.DEFAULT_DEPTH_LIMIT
        self.heuristic = "manhattan"
        self.note = ""
        self._back = False
        R = self.rect
        self.count_buttons = {}
        for i, n in enumerate(COUNT_CHOICES):
            self.count_buttons[n] = Button((R.x + 24 + i * 78, R.y + 62, 72, 30), f"{n} maps",
                                           lambda v=n: self.set_count(v))
        self.run_button = Button((R.x + 24 + 4 * 78 + 10, R.y + 62, 110, 30), "Run (Space)", self.start)
        self.seed_button = Button((R.x + 24 + 4 * 78 + 130, R.y + 62, 120, 30), "New seed (N)", self.new_seed)
        self.save_button = Button((R.x + 24 + 4 * 78 + 260, R.y + 62, 120, 30), "Save CSV (S)", self.save)
        self.metric_button = Button((R.right - 360, R.y + 62, 240, 30), "", self.next_metric)
        self.back_button = Button((R.right - 110, R.y + 62, 94, 30), "Back (Esc)", lambda: setattr(self, "_back", True))
        self.buttons = (list(self.count_buttons.values()) + [self.run_button, self.seed_button,
                        self.save_button, self.metric_button, self.back_button])

    # ------------------------------------------------------------- control
    def open(self, depth_limit, heuristic):
        self.depth_limit, self.heuristic = depth_limit, heuristic
        self._back = False
        self.start()

    def set_count(self, n):
        self.count = n
        self.start()

    def start(self):
        self.bench = Benchmark(self.count, self.seed, self.depth_limit, self.heuristic)
        self.note = ""

    def new_seed(self):
        self.seed += self.count
        self.start()

    def next_metric(self):
        self.metric = (self.metric + 1) % len(self.METRICS)

    def save(self):
        if self.bench and self.bench.records:
            paths = self.bench.save_csv(self.results_dir)
            self.note = "Saved: results/" + " and results/".join(p.replace("\\", "/").split("/")[-1] for p in paths)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            for b in self.buttons:
                if b.handle(event):
                    self.sound.play("click")
                    break
        elif event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self._back = True
            elif k in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
            elif k == pygame.K_n:
                self.new_seed()
            elif k == pygame.K_s:
                self.save()
            elif k == pygame.K_TAB:
                self.next_metric()
        if self._back:
            self._back = False
            return "back"
        return None

    def update(self, dt):
        """Run maps in small slices so the window stays responsive."""
        if self.bench and not self.bench.done:
            t0 = perf_counter()
            while not self.bench.done and perf_counter() - t0 < 0.03:
                self.bench.step()
            if self.bench.done:
                self.sound.play("win")

    # ------------------------------------------------------------- drawing
    def draw(self, surf):
        small, normal, big, tiny = (self.fonts[k] for k in ("small", "normal", "big", "tiny"))
        R = self.rect
        surf.fill(COL["bg"])
        pygame.draw.rect(surf, COL["panel"], R, border_radius=12)
        pygame.draw.rect(surf, COL["panel_edge"], R, 2, border_radius=12)
        draw_text(surf, "Benchmark Mode", big, COL["accent"], (R.x + 24, R.y + 12))
        b = self.bench
        sub = (f"{b.count} random dungeons ({b.width}x{b.height}), seeds {b.seed}-{b.seed + b.count - 1}   |   "
               f"DLS limit {b.depth_limit}   |   heuristic {HEURISTIC_LABELS[b.heuristic]}") if b else ""
        draw_text(surf, sub, small, COL["muted"], (R.x + 24, R.y + 42))

        for n, btn in self.count_buttons.items():
            btn.selected = b is not None and b.count == n
        self.metric_button.label = f"Bars: {self.METRICS[self.metric][0]} (Tab)"
        for btn in self.buttons:
            btn.draw(surf, small)
        if self.note:
            draw_text(surf, self.note, tiny, COL["good"], (R.right - 24, R.y + 22), "topright")
        if b is None:
            return

        # --- progress bar
        bar = pygame.Rect(R.x + 24, R.y + 106, R.w - 48, 16)
        pygame.draw.rect(surf, COL["bg"], bar, border_radius=8)
        fill = bar.copy()
        fill.w = max(4, int(bar.w * b.progress))
        pygame.draw.rect(surf, COL["good"] if b.done else COL["frontier"], fill, border_radius=8)
        msg = (f"Done: {b.maps_done} maps in {b.elapsed:.1f} s" if b.done
               else f"Running... {b.maps_done} / {b.count} maps")
        draw_text(surf, msg, tiny, (20, 20, 30), bar.center, "center")

        # --- table
        summary = b.summary()
        top = R.y + 140
        for title, x, key, _fmt in self.COLUMNS:
            draw_text(surf, title, small, COL["info"], (R.x + x, top))
        draw_text(surf, f"{self.METRICS[self.metric][0]} (bars)", small, COL["info"], (R.x + self.BAR_X, top))
        pygame.draw.line(surf, COL["panel_edge"], (R.x + 16, top + 22), (R.right - 16, top + 22))

        metric_key = self.METRICS[self.metric][1]
        values = {n: (summary[n][metric_key] or 0) for n in summary}
        max_val = max(values.values(), default=1) or 1

        def best(key, lowest=True):
            pool = [m[key] for m in summary.values() if m[key] is not None]
            return (min(pool) if lowest else max(pool)) if pool else None

        bests = {"avg_cost": best("avg_cost"), "cost_ratio": best("cost_ratio"),
                 "avg_length": best("avg_length"), "avg_expanded": best("avg_expanded"),
                 "avg_frontier": best("avg_frontier"), "avg_time_ms": best("avg_time_ms"),
                 "solved_pct": best("solved_pct", False), "optimal_pct": best("optimal_pct", False)}
        y = top + 34
        for name, m in summary.items():
            draw_text(surf, name, normal, COL["text"], (R.x + 24, y))
            for title, x, key, fmt in self.COLUMNS[1:]:
                v = m[key]
                text = "-" if v is None else fmt.format(v)
                good = v is not None and bests.get(key) is not None and abs(v - bests[key]) < 1e-9
                color = COL["good"] if good and key in ("avg_cost", "cost_ratio", "solved_pct", "optimal_pct") \
                    else (COL["info"] if good else COL["text"])
                draw_text(surf, text, normal, color, (R.x + x, y))
            width = int((R.w - self.BAR_X - 40) * values[name] / max_val)
            pygame.draw.rect(surf, COL["explored"], (R.x + self.BAR_X, y + 2, max(width, 2), 16), border_radius=4)
            y += 34

        # --- conclusions
        box = pygame.Rect(R.x + 24, y + 14, R.w - 48, R.bottom - y - 38)
        pygame.draw.rect(surf, COL["bg"], box, border_radius=10)
        pygame.draw.rect(surf, COL["panel_edge"], box, 1, border_radius=10)
        draw_text(surf, "What the data says" if b.done else "Running - conclusions appear when finished",
                  normal, COL["accent"], (box.x + 14, box.y + 10))
        if b.done:
            ly = box.y + 40
            for line in b.insights():
                for wrapped in wrap_text(line, normal, box.w - 40)[:2]:
                    draw_text(surf, "- " + wrapped if wrapped is line or wrapped == line else "  " + wrapped,
                              normal, COL["text"], (box.x + 14, ly))
                    ly += 24
        draw_text(surf, "Green = best cost / highest success    Cyan = fewest nodes, steps, frontier or time    "
                  "Averages for cost and steps use solved maps only", tiny, COL["muted"],
                  (R.x + 24, R.bottom - 22))
