"""Small UI toolkit: buttons, text helpers and the comparison dashboard."""
from dataclasses import dataclass

import pygame

from .search import SearchResult
from .settings import COLORS


# --------------------------------------------------------------- text
def draw_text(surface, text, font, color, pos, anchor="topleft"):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)
    return rect


def wrap_text(text, font, max_width):
    """Split `text` into lines that fit inside `max_width` pixels."""
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ------------------------------------------------------------- button
class Button:
    def __init__(self, rect, label, callback):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.selected = False
        self.enabled = True

    def handle(self, event):
        """Returns True if the click was consumed."""
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.enabled and self.rect.collidepoint(event.pos)):
            self.callback()
            return True
        return False

    def draw(self, surface, font):
        hovered = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        if not self.enabled:
            bg, fg = COLORS["button_off"], COLORS["muted"]
        elif self.selected:
            bg, fg = COLORS["button_sel"], (30, 22, 10)
        else:
            bg = COLORS["button_hover"] if hovered else COLORS["button"]
            fg = COLORS["text"]
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, COLORS["panel_edge"], self.rect, 1, border_radius=6)
        draw_text(surface, self.label, font, fg, self.rect.center, "center")


# ---------------------------------------------------------- dashboard
@dataclass
class Row:
    label: str
    result: SearchResult
    algorithm: str
    heuristic: str


class Dashboard:
    """Full-screen modal that compares algorithms / heuristics on the current dungeon."""

    METRICS = [
        ("Expanded nodes", lambda r: r.expanded),
        ("Path cost", lambda r: r.cost if r.found else 0),
        ("Peak frontier", lambda r: r.max_frontier),
        ("Time (ms)", lambda r: r.time_ms),
    ]
    COLUMNS = [  # (title, x offset, key)
        ("Method", 24, "label"),
        ("Status", 250, "status"),
        ("Length", 372, "length"),
        ("Cost", 446, "cost"),
        ("Expanded", 520, "expanded"),
        ("Frontier", 624, "frontier"),
        ("Time (ms)", 716, "time"),
    ]
    BAR_X = 830

    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.subtitle = ""
        self.pages = []          # each: {"title": str, "rows": [Row], "footer": str}
        self.page = 0
        self.metric = 0
        self.note = ""
        self.row_rects = []
        self.tab_rects = []
        self.close_button = Button((self.rect.right - 110, self.rect.y + 14, 94, 30),
                                   "Close", lambda: None)
        self.metric_button = Button((self.rect.right - 330, self.rect.y + 14, 206, 30),
                                    "", lambda: None)

    # ------------------------------------------------------------ data
    def set_pages(self, subtitle, pages):
        self.subtitle = subtitle
        self.pages = pages
        self.page = 0
        self.note = ""

    @property
    def rows(self):
        return self.pages[self.page]["rows"] if self.pages else []

    def all_rows(self):
        for page in self.pages:
            for row in page["rows"]:
                yield page["title"], row

    def next_metric(self):
        self.metric = (self.metric + 1) % len(self.METRICS)

    def next_page(self):
        if self.pages:
            self.page = (self.page + 1) % len(self.pages)

    def row_at(self, pos):
        for rect, row in self.row_rects:
            if rect.collidepoint(pos):
                return row
        return None

    def tab_at(self, pos):
        for i, rect in enumerate(self.tab_rects):
            if rect.collidepoint(pos):
                return i
        return None

    # ------------------------------------------------------------ draw
    def draw(self, surface, fonts):
        small, normal, big = fonts["small"], fonts["normal"], fonts["big"]
        R = self.rect

        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((8, 6, 14, 225))
        surface.blit(dim, (0, 0))

        pygame.draw.rect(surface, COLORS["panel"], R, border_radius=12)
        pygame.draw.rect(surface, COLORS["panel_edge"], R, 2, border_radius=12)
        draw_text(surface, "Performance Comparison Dashboard", big, COLORS["accent"], (R.x + 24, R.y + 14))
        draw_text(surface, self.subtitle, small, COLORS["muted"], (R.x + 24, R.y + 46))
        self.metric_button.label = f"Bars: {self.METRICS[self.metric][0]}  (Tab)"
        self.metric_button.draw(surface, small)
        self.close_button.draw(surface, normal)
        if self.note:
            draw_text(surface, self.note, small, COLORS["good"], (R.right - 24, R.y + 50), "topright")

        # --- tabs
        self.tab_rects = []
        for i, page in enumerate(self.pages):
            tab = pygame.Rect(R.x + 24 + i * 250, R.y + 74, 240, 28)
            self.tab_rects.append(tab)
            active = i == self.page
            pygame.draw.rect(surface, COLORS["button_sel"] if active else COLORS["button"], tab, border_radius=6)
            draw_text(surface, page["title"], small, (30, 22, 10) if active else COLORS["text"],
                      tab.center, "center")

        top = R.y + 116
        for title, x, _key in self.COLUMNS:
            draw_text(surface, title, small, COLORS["info"], (R.x + x, top))
        draw_text(surface, f"{self.METRICS[self.metric][0]} (bars)", small, COLORS["info"],
                  (R.x + self.BAR_X, top))
        pygame.draw.line(surface, COLORS["panel_edge"], (R.x + 16, top + 22), (R.right - 16, top + 22), 1)

        rows = self.rows
        found = [r.result for r in rows if r.result.found]
        best_cost = min((r.cost for r in found), default=None)
        best_len = min((r.length for r in found), default=None)
        best_exp = min((r.expanded for r in found), default=None)
        best_front = min((r.max_frontier for r in found), default=None)
        metric_fn = self.METRICS[self.metric][1]
        max_val = max((metric_fn(r.result) for r in rows), default=1) or 1

        mouse = pygame.mouse.get_pos()
        self.row_rects = []
        row_h = 38
        y = top + 34
        for row in rows:
            res = row.result
            rect = pygame.Rect(R.x + 12, y - 6, R.w - 24, row_h - 2)
            self.row_rects.append((rect, row))
            if rect.collidepoint(mouse):
                pygame.draw.rect(surface, COLORS["button"], rect, border_radius=6)

            status = {"success": "Success", "failure": "No path", "depth_limit": "Depth limit"}[res.status]
            ok = res.found
            cells = {
                "label": (row.label, COLORS["text"]),
                "status": (status, COLORS["good"] if ok else COLORS["bad"]),
                "length": (res.length if ok else "-",
                           COLORS["good"] if ok and res.length == best_len else COLORS["text"]),
                "cost": (f"{res.cost:g}" if ok else "-",
                         COLORS["good"] if ok and res.cost == best_cost else COLORS["text"]),
                "expanded": (res.expanded,
                             COLORS["info"] if ok and res.expanded == best_exp else COLORS["text"]),
                "frontier": (res.max_frontier,
                             COLORS["info"] if ok and res.max_frontier == best_front else COLORS["text"]),
                "time": (f"{res.time_ms:.2f}", COLORS["text"]),
            }
            for _title, x, key in self.COLUMNS:
                text, color = cells[key]
                draw_text(surface, text, normal, color, (R.x + x, y))

            val = metric_fn(res)
            bar_w = int((R.w - self.BAR_X - 36) * val / max_val)
            bar = pygame.Rect(R.x + self.BAR_X, y + 2, max(bar_w, 2), 16)
            pygame.draw.rect(surface, COLORS["explored"] if ok else COLORS["bad"], bar, border_radius=4)
            y += row_h

        foot = R.bottom - 84
        page = self.pages[self.page] if self.pages else {"footer": ""}
        for i, line in enumerate(wrap_text(page["footer"], small, R.w - 48)[:2]):
            draw_text(surface, line, small, COLORS["accent"], (R.x + 24, foot + i * 20))
        draw_text(surface, "Green = best cost / fewest steps    Cyan = fewest nodes / smallest frontier    "
                  "Red = no solution", small, COLORS["muted"], (R.x + 24, foot + 44))
        draw_text(surface, "Click a row to load it  |  Tab = change bars  |  Left/Right = switch page  |  "
                  "S = save CSV  |  Esc or C = close", small, COLORS["muted"], (R.x + 24, foot + 64))
