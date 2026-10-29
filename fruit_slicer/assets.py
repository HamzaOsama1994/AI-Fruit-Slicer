"""Game assets made in code: fruit and bomb images, bilingual text, and sound effects (no files to license)."""

from __future__ import annotations

import math

import arabic_reshaper
import cv2
import numpy as np
import pygame
from bidi.algorithm import get_display

FRUITS = {  # r = radius in px; (sx, sy) = oval shape; flesh = juice colour
    "watermelon": dict(r=60, sx=1.08, sy=0.95, flesh=(235, 55, 70)),
    "orange": dict(r=46, sx=1.0, sy=1.0, flesh=(255, 165, 40)),
    "apple": dict(r=44, sx=1.06, sy=0.96, flesh=(250, 238, 195)),
    "kiwi": dict(r=40, sx=1.15, sy=0.9, flesh=(120, 190, 50)),
    "lemon": dict(r=40, sx=1.22, sy=0.86, flesh=(250, 235, 110)),
}
BOMB_R = 44
LIGHT = np.array([-0.45, -0.55, 0.70]) / np.linalg.norm([-0.45, -0.55, 0.70])  # from the top-left, towards the viewer


def _noise(h: int, w: int, rng: np.random.Generator, scale: float) -> np.ndarray:
    """Smooth random texture in 0..1; scale = feature size in px."""
    small = rng.random((max(2, int(h / scale)), max(2, int(w / scale)))).astype(np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC).clip(0, 1)


def _to_surface(rgb: np.ndarray, alpha: np.ndarray) -> pygame.Surface:
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 1) * 255]).astype(np.uint8)
    return pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA").copy()


def _sphere(r: int, sx: float, sy: float):
    """Normals of a lit (oval) ball filling a w x h image: what makes a flat colour look round."""
    w, h = int(2 * r * sx) + 2, int(2 * r * sy) + 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    nx, ny = (xx - w / 2) / (r * sx), (yy - h / 2) / (r * sy)
    d = np.sqrt(nx ** 2 + ny ** 2)
    nz = np.sqrt(np.clip(1 - d ** 2, 0, 1))
    alpha = np.clip((1 - d) * r * min(sx, sy), 0, 1)  # anti-aliased edge
    return nx, ny, nz, alpha


def _lit(albedo: np.ndarray, nx, ny, nz, gloss: float, sharp: float = 40) -> np.ndarray:
    diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    half = LIGHT + np.array([0, 0, 1.0])
    half /= np.linalg.norm(half)
    spec = np.clip(nx * half[0] + ny * half[1] + nz * half[2], 0, 1) ** sharp
    rim = 0.75 + 0.25 * nz  # edges turn away from the light
    return albedo * ((0.38 + 0.72 * diffuse) * rim)[..., None] + (spec * gloss * 255)[..., None]


def _mix(a, b, t: np.ndarray) -> np.ndarray:
    return np.asarray(a, np.float32) * (1 - t[..., None]) + np.asarray(b, np.float32) * t[..., None]


def _rng(kind: str, salt: int = 0) -> np.random.Generator:
    return np.random.default_rng(sum(map(ord, kind)) * 7 + salt)  # same look every run


def whole(kind: str) -> pygame.Surface:
    f = FRUITS[kind]
    rng = _rng(kind)
    nx, ny, nz, alpha = _sphere(f["r"], f["sx"], f["sy"])
    h, w = alpha.shape
    if kind == "watermelon":
        lon = np.arctan2(nx, nz + 1e-6)  # stripes run pole to pole and wobble like the real ones
        wobble = 0.5 * np.sin(ny * 9 + rng.uniform(0, 6)) + 0.6 * (_noise(h, w, rng, 10) - 0.5)
        stripe = cv2.GaussianBlur((np.sin(lon * 8 + wobble) > 0.15).astype(np.float32), (0, 0), 1.2)
        albedo = _mix((130, 185, 80), (24, 92, 38), stripe) * (0.9 + 0.2 * _noise(h, w, rng, 4))[..., None]
        rgb = _lit(albedo, nx, ny, nz, gloss=0.35, sharp=25)
    elif kind in ("orange", "lemon"):
        base = (255, 140, 15) if kind == "orange" else (250, 215, 35)
        pores = 0.88 + 0.12 * _noise(h, w, rng, 2.2)
        rgb = _lit(np.asarray(base, np.float32) * pores[..., None], nx, ny, nz, gloss=0.45, sharp=30)
    elif kind == "apple":
        streaks = _noise(h, w, rng, 6) * np.clip(0.3 + ny, 0, 1)  # yellow streaks towards the bottom
        albedo = _mix((200, 22, 35), (225, 120, 45), np.clip(streaks * 0.7, 0, 0.45))
        rgb = _lit(albedo, nx, ny, nz, gloss=0.7, sharp=50)
    else:  # kiwi: matt and fuzzy
        fuzz = 0.75 + 0.35 * _noise(h, w, rng, 1.3)
        rgb = _lit(np.asarray((128, 92, 52), np.float32) * fuzz[..., None], nx, ny, nz, gloss=0.05)
    surf = _to_surface(rgb, alpha)
    cx, top = w // 2, int(h / 2 - f["r"] * f["sy"])
    if kind == "apple":  # stem, leaf and the dip they sit in: add room above the fruit first
        room = pygame.Surface((w + 20, h + 24), pygame.SRCALPHA)
        room.blit(surf, (10, 12))  # keeps the fruit centred so rotation still spins round its middle
        surf, cx, top = room, cx + 10, top + 12
        pygame.draw.circle(surf, (120, 20, 25, 160), (cx, top + 9), 6)
        pygame.draw.line(surf, (90, 55, 25), (cx, top + 10), (cx + 5, top - 4), 4)
        pygame.draw.ellipse(surf, (60, 150, 55), (cx + 4, top - 8, 22, 10))
    if kind == "lemon":  # pointed ends
        for x in (1, w - 8):
            pygame.draw.ellipse(surf, (225, 190, 25), (x, h // 2 - 5, 7, 10))
    return surf


def cross_section(kind: str) -> pygame.Surface:
    """The cut face: flesh, rind and seeds (the two halves are the left/right sides of this)."""
    f = FRUITS[kind]
    rng = _rng(kind, 1)
    r = f["r"]
    n = 2 * r + 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    dx, dy = (xx - n / 2) / r, (yy - n / 2) / r
    d, ang = np.sqrt(dx ** 2 + dy ** 2), np.arctan2(dy, dx)
    alpha = np.clip((1 - d) * r, 0, 1)
    juice = 0.92 + 0.12 * _noise(n, n, rng, 3)  # wet, uneven flesh
    if kind == "watermelon":
        flesh = _mix((250, 80, 90), (215, 35, 55), np.clip(d / 0.8, 0, 1)) * juice[..., None]
        rind = _mix((210, 240, 180), (40, 110, 45), np.clip((d - 0.8) / 0.2, 0, 1) ** 2)
        rgb = np.where((d > 0.8)[..., None], rind, flesh)
    elif kind in ("orange", "lemon"):
        peel, pulp = ((255, 140, 15), (255, 170, 45)) if kind == "orange" else ((245, 210, 30), (250, 238, 120))
        segment = np.abs(np.sin(ang * 5))  # 10 segments with pale membranes between
        flesh = _mix((255, 245, 225), pulp, np.clip(segment * 6, 0, 1)) * juice[..., None]
        flesh = np.where((d < 0.1)[..., None], np.float32(250), flesh)
        rind = _mix((255, 245, 225), peel, np.clip((d - 0.82) / 0.1, 0, 1))
        rgb = np.where((d > 0.82)[..., None], rind, flesh)
    elif kind == "apple":
        flesh = _mix((255, 248, 215), (240, 225, 175), np.clip(d, 0, 1)) * juice[..., None]
        core = np.abs(np.cos(ang * 2.5)) * 0.35 + 0.12 > d  # five-point star core
        flesh = np.where(core[..., None], _mix((235, 215, 160), (210, 185, 130), np.clip(d / 0.5, 0, 1)), flesh)
        rgb = np.where((d > 0.93)[..., None], np.float32([200, 22, 35]), flesh)
    else:  # kiwi
        rays = 0.85 + 0.15 * np.abs(np.sin(ang * 24))
        flesh = _mix((200, 230, 120), (95, 165, 35), np.clip((d - 0.2) / 0.7, 0, 1)) * (juice * rays)[..., None]
        flesh = np.where((d < 0.22)[..., None], np.float32([245, 245, 215]), flesh)
        rgb = np.where((d > 0.93)[..., None], np.float32([128, 92, 52]), flesh)
    rgb = rgb * (1.08 - 0.15 * np.clip(dx + dy + 0.6, 0, 1.4))[..., None]  # light falls from the top-left
    surf = _to_surface(rgb, alpha)
    c = n / 2
    if kind == "watermelon":
        for _ in range(16):
            a, dd = rng.uniform(0, math.tau), rng.uniform(0.35, 0.62) * r
            pygame.draw.ellipse(surf, (30, 20, 20), (c + math.cos(a) * dd - 3, c + math.sin(a) * dd - 4, 6, 9))
    elif kind == "kiwi":
        for i in range(26):
            a, dd = i * math.tau / 26 + rng.uniform(-0.05, 0.05), r * rng.uniform(0.3, 0.38)
            pygame.draw.circle(surf, (20, 20, 15), (c + math.cos(a) * dd, c + math.sin(a) * dd), 2)
    elif kind == "apple":
        for i in range(5):
            a = i * math.tau / 5 + 0.3
            pygame.draw.ellipse(surf, (95, 55, 25), (c + math.cos(a) * 9 - 3, c + math.sin(a) * 9 - 4, 6, 8))
    for _ in range(6):  # juicy glints
        a, dd = rng.uniform(0, math.tau), rng.uniform(0.15, 0.7) * r
        pygame.draw.circle(surf, (255, 252, 238), (c + math.cos(a) * dd, c + math.sin(a) * dd), 1)
    return surf


def halves(kind: str) -> tuple[pygame.Surface, pygame.Surface]:
    cut = cross_section(kind)
    w, h = cut.get_size()
    return cut.subsurface((0, 0, w // 2, h)).copy(), cut.subsurface((w // 2, 0, w - w // 2, h)).copy()


def bomb() -> pygame.Surface:
    r = BOMB_R
    nx, ny, nz, alpha = _sphere(r, 1.0, 1.0)
    metal = 0.9 + 0.2 * _noise(*alpha.shape, _rng("bomb"), 5)
    body = _to_surface(_lit(np.asarray((48, 48, 56), np.float32) * metal[..., None], nx, ny, nz, gloss=0.9, sharp=60),
                       alpha)
    s = pygame.Surface((2 * r + 20, 2 * r + 20), pygame.SRCALPHA)
    c = (r + 10, r + 16)
    s.blit(body, body.get_rect(center=c))
    pygame.draw.circle(s, (220, 30, 30), c, r, 3)  # red ring so it reads as danger at a glance
    pygame.draw.rect(s, (110, 110, 120), (c[0] - 9, c[1] - r - 8, 18, 12), border_radius=3)
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


_labels: dict[tuple, pygame.Surface] = {}  # shaping Arabic and rendering text every frame cost ~5 ms/frame


def text(surf: pygame.Surface, s: str, size: int, pos: tuple[float, float],
         color=(255, 255, 255), anchor: str = "center") -> pygame.Rect:
    key = (s, size, tuple(color))
    if key not in _labels:
        img = _font(size).render(shape(s), True, color)
        label = pygame.Surface((img.get_width() + 3, img.get_height() + 3), pygame.SRCALPHA)
        label.blit(_font(size).render(shape(s), True, (0, 0, 0)), (3, 3))  # drop shadow
        label.blit(img, (0, 0))
        _labels[key] = label
    rect = _labels[key].get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surf.blit(_labels[key], rect)
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
