"""Procedural sprites (no image files needed) and a tiny particle system."""
import math
import random

import pygame

from .settings import COLORS as COL


# --------------------------------------------------------------- sprites
def draw_key(surf, center, cs, t=0.0):
    """Golden key that gently floats. `cs` is the cell size in pixels."""
    s = cs / 32
    cx, cy = center
    cy += int(math.sin(t * 3.0) * 2 * s)
    pygame.draw.circle(surf, (120, 90, 20), (cx, cy - int(5 * s)), max(4, int(8 * s)), 2)
    pygame.draw.circle(surf, COL["key"], (cx, cy - int(5 * s)), max(3, int(6 * s)), 2)
    pygame.draw.line(surf, COL["key"], (cx, cy + int(1 * s)), (cx, cy + int(11 * s)), 2)
    pygame.draw.line(surf, COL["key"], (cx, cy + int(8 * s)), (cx + int(5 * s), cy + int(8 * s)), 2)
    pygame.draw.line(surf, COL["key"], (cx, cy + int(11 * s)), (cx + int(4 * s), cy + int(11 * s)), 2)


def draw_chest(surf, rect, unlocked, t=0.0):
    """Treasure chest; padlocked until the key is collected, glowing afterwards."""
    if unlocked:
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)
        glow = (255, int(190 + 50 * pulse), int(60 + 60 * pulse))
        pygame.draw.rect(surf, glow, rect.inflate(2, 2), 2, border_radius=6)
    body = rect.inflate(-6, -10)
    body.y += 2
    pygame.draw.rect(surf, COL["chest"], body, border_radius=4)
    lid = pygame.Rect(body.x, body.y, body.w, body.h // 2)
    pygame.draw.rect(surf, (140, 86, 40), lid, border_radius=4)
    pygame.draw.rect(surf, COL["chest_band"], pygame.Rect(body.centerx - 2, body.y, 4, body.h))
    pygame.draw.rect(surf, COL["chest_band"], body, 1, border_radius=4)
    if not unlocked:
        lock = pygame.Rect(0, 0, max(8, rect.w // 4), max(7, rect.w // 4 - 1))
        lock.center = (body.centerx, body.centery + 1)
        pygame.draw.rect(surf, COL["lock"], lock, border_radius=2)
        pygame.draw.circle(surf, COL["lock"], (lock.centerx, lock.y), max(3, rect.w // 10), 1)


def draw_explorer(surf, center, cs, has_key, t=0.0, moving=False):
    """Little round adventurer that bobs while walking."""
    cx, cy = center
    bob = int(math.sin(t * 14.0) * max(1, cs // 16)) if moving else 0
    radius = max(5, int(cs * 0.34))
    cy += bob
    pygame.draw.ellipse(surf, (10, 10, 16), (cx - radius, cy + radius - 2 - bob, radius * 2, max(3, radius // 2)))
    pygame.draw.circle(surf, (10, 60, 56), (cx, cy), radius + 2)
    pygame.draw.circle(surf, COL["explorer"], (cx, cy), radius)
    pygame.draw.circle(surf, (170, 255, 245), (cx - radius // 3, cy - radius // 3), max(2, radius // 4))
    eye = max(1, radius // 4)
    pygame.draw.circle(surf, (10, 30, 30), (cx - eye * 2, cy - eye + 1), eye)
    pygame.draw.circle(surf, (10, 30, 30), (cx + eye * 2, cy - eye + 1), eye)
    if has_key:
        pygame.draw.circle(surf, COL["key"], (cx, cy + radius // 2), max(2, radius // 3))


def draw_star(surf, center, radius, color, width=0):
    """Five-pointed star (filled when width == 0)."""
    cx, cy = center
    pts = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    pygame.draw.polygon(surf, color, pts, width)


# ------------------------------------------------------------- particles
class Particles:
    """Confetti / sparkles. Each particle: [x, y, vx, vy, life, max_life, color, size, gravity]."""

    def __init__(self):
        self.items = []

    def burst(self, pos, colors, n=24, speed=140, life=0.9, gravity=260, size=3):
        for _ in range(n):
            ang = random.uniform(0, 2 * math.pi)
            sp = random.uniform(0.3, 1.0) * speed
            life_i = random.uniform(0.5, 1.0) * life
            self.items.append([pos[0], pos[1], math.cos(ang) * sp, math.sin(ang) * sp - speed * 0.3,
                               life_i, life_i, random.choice(colors), size, gravity])

    def update(self, dt):
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            p[4] -= dt
        self.items = [p for p in self.items if p[4] > 0]

    def draw(self, surf):
        for p in self.items:
            frac = p[4] / p[5]
            radius = max(1, int(p[7] * (0.4 + frac)))
            pygame.draw.circle(surf, p[6], (int(p[0]), int(p[1])), radius)
