"""Game assets made in code: fruit and bomb images, bilingual text, and sound effects (no files to license)."""

from __future__ import annotations

import math
import random

import arabic_reshaper
import numpy as np
import pygame
from bidi.algorithm import get_display

FRUITS = {
    "watermelon": dict(r=60, skin=(46, 139, 60), stripe=(22, 92, 36), rind=(225, 245, 200), flesh=(235, 55, 70)),
    "orange": dict(r=46, skin=(255, 145, 20), stripe=None, rind=(255, 235, 190), flesh=(255, 175, 50)),
    "apple": dict(r=44, skin=(210, 30, 45), stripe=None, rind=(255, 245, 215), flesh=(250, 238, 195)),
    "kiwi": dict(r=40, skin=(135, 98, 52), stripe=None, rind=(150, 200, 70), flesh=(110, 185, 45)),
    "lemon": dict(r=40, skin=(250, 222, 45), stripe=None, rind=(255, 250, 210), flesh=(250, 238, 120)),
}
BOMB_R = 44


def _circle_clip(surf: pygame.Surface, r: int) -> pygame.Surface:
    mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


def _darker(c, f=0.65):
    return tuple(int(v * f) for v in c)


def whole(kind: str) -> pygame.Surface:
    f, rng = FRUITS[kind], random.Random(kind)
    r = f["r"]
    s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    pygame.draw.circle(s, f["skin"], (r, r), r)
    if f["stripe"]:  # watermelon stripes
        for i in range(-3, 4):
            pygame.draw.ellipse(s, f["stripe"], (r + i * r * 0.32 - 6, -4, 12, 2 * r + 8))
    if kind == "kiwi":  # fuzzy speckles
        for _ in range(60):
            pygame.draw.circle(s, _darker(f["skin"], 0.8), (rng.randint(0, 2 * r), rng.randint(0, 2 * r)), 1)
    pygame.draw.circle(s, _darker(f["skin"]), (r, r), r, 3)
    s = _circle_clip(s, r)
    pygame.draw.ellipse(s, (255, 255, 255, 90), (r * 0.45, r * 0.35, r * 0.55, r * 0.35))  # highlight
    if kind == "apple":
        pygame.draw.line(s, (95, 60, 30), (r, r * 0.25), (r + 4, 2), 4)
        pygame.draw.ellipse(s, (60, 160, 60), (r + 4, 2, 18, 9))
    return s


def cross_section(kind: str) -> pygame.Surface:
    """What the fruit looks like cut in half (the halves are the left/right sides of this)."""
    f, rng = FRUITS[kind], random.Random(kind)
    r = f["r"]
    s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    pygame.draw.circle(s, f["skin"], (r, r), r)
    pygame.draw.circle(s, f["rind"], (r, r), int(r * 0.9))
    pygame.draw.circle(s, f["flesh"], (r, r), int(r * 0.8))
    if kind in ("orange", "lemon"):  # segments
        for i in range(10):
            a = i * math.tau / 10
            pygame.draw.line(s, f["rind"], (r, r), (r + math.cos(a) * r * 0.8, r + math.sin(a) * r * 0.8), 2)
    elif kind == "watermelon":
        for _ in range(14):
            a, d = rng.uniform(0, math.tau), rng.uniform(0.25, 0.6) * r
            pygame.draw.ellipse(s, (25, 20, 20), (r + math.cos(a) * d - 3, r + math.sin(a) * d - 4, 6, 9))
    elif kind == "kiwi":
        pygame.draw.circle(s, (240, 240, 210), (r, r), int(r * 0.28))
        for i in range(18):
            a = i * math.tau / 18
            pygame.draw.circle(s, (20, 20, 15), (r + math.cos(a) * r * 0.4, r + math.sin(a) * r * 0.4), 2)
    elif kind == "apple":
        for i in range(5):
            a = i * math.tau / 5
            pygame.draw.ellipse(s, (110, 70, 35), (r + math.cos(a) * 8 - 3, r + math.sin(a) * 8 - 4, 6, 8))
    return s


def halves(kind: str) -> tuple[pygame.Surface, pygame.Surface]:
    cut = cross_section(kind)
    w, h = cut.get_size()
    return cut.subsurface((0, 0, w // 2, h)).copy(), cut.subsurface((w // 2, 0, w - w // 2, h)).copy()


def bomb() -> pygame.Surface:
    r = BOMB_R
    s = pygame.Surface((2 * r + 20, 2 * r + 20), pygame.SRCALPHA)
    c = (r + 10, r + 16)
    pygame.draw.circle(s, (35, 35, 40), c, r)
    pygame.draw.circle(s, (200, 30, 30), c, r, 4)  # red ring so it reads as danger at a glance
    pygame.draw.ellipse(s, (255, 255, 255, 70), (c[0] - r * 0.6, c[1] - r * 0.65, r * 0.6, r * 0.35))
    pygame.draw.rect(s, (80, 80, 85), (c[0] - 9, c[1] - r - 8, 18, 12), border_radius=3)
    pygame.draw.arc(s, (150, 110, 60), (c[0], c[1] - r - 22, 24, 30), math.pi * 0.5, math.pi, 4)
    return s


def heart(surf: pygame.Surface, center: tuple[int, int], size: int, filled: bool) -> None:
    x, y = center
    color = (235, 45, 70) if filled else (90, 90, 100)
    r = size // 4
    pygame.draw.circle(surf, color, (x - r, y - r // 2), r)
    pygame.draw.circle(surf, color, (x + r, y - r // 2), r)
    pygame.draw.polygon(surf, color, [(x - 2 * r, y - r // 3), (x + 2 * r, y - r // 3), (x, y + 2 * r)])


# ── Text ──────────────────────────────────────────────────────────────────────
_fonts: dict[int, pygame.font.Font] = {}


def _font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("segoeui,tahoma,arial", size, bold=True)  # all have Arabic glyphs
    return _fonts[size]


def shape(text: str) -> str:
    """Join Arabic letters and order right-to-left; English passes through unchanged."""
    if any("؀" <= ch <= "ۿ" for ch in text):
        return get_display(arabic_reshaper.reshape(text))
    return text


def text(surf: pygame.Surface, s: str, size: int, pos: tuple[float, float],
         color=(255, 255, 255), anchor: str = "center") -> pygame.Rect:
    img = _font(size).render(shape(s), True, color)
    shadow = _font(size).render(shape(s), True, (0, 0, 0))
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surf.blit(shadow, rect.move(3, 3))
    surf.blit(img, rect)
    return rect


# ── Sound ─────────────────────────────────────────────────────────────────────
class _Silent:
    def play(self) -> None:
        pass


def sounds() -> dict:
    names = ("slice", "bomb", "start", "over")
    if not pygame.mixer.get_init():
        return {n: _Silent() for n in names}
    sr, rng = 44100, np.random.default_rng(0)

    def t(d):
        return np.linspace(0, d, int(sr * d), endpoint=False)

    def make(x):
        a = (np.clip(x, -1, 1) * 32767 * 0.5).astype(np.int16)
        return pygame.sndarray.make_sound(np.ascontiguousarray(np.repeat(a[:, None], 2, axis=1)))

    def tones(freqs, d):
        tt = t(d)
        return np.concatenate([np.sin(2 * np.pi * f * tt) * np.exp(-tt * 12) for f in freqs])

    ts, tb = t(0.15), t(0.8)
    swoosh = np.sin(2 * np.pi * np.cumsum(np.linspace(1800, 400, ts.size)) / sr) * 0.4
    boom_noise = np.convolve(rng.uniform(-1, 1, tb.size), np.ones(60) / 10, "same")
    return {
        "slice": make((swoosh + rng.uniform(-1, 1, ts.size) * 0.6) * np.exp(-ts * 25)),
        "bomb": make(boom_noise * np.exp(-tb * 5) + np.sin(2 * np.pi * 55 * tb) * np.exp(-tb * 4) * 0.6),
        "start": make(tones([660, 990], 0.15)),
        "over": make(tones([523, 392, 262], 0.2)),
    }
