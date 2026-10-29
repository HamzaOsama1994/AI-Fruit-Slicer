"""Pure game rules and physics (no pygame, no camera) so they can be unit-tested."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

GRAVITY = 900.0          # px/s^2
MIN_SLICE_SPEED = 500.0  # px/s: slower finger movement does not cut


@dataclass
class Body:
    """Anything that flies: a fruit, a bomb, or a sliced half."""
    x: float
    y: float
    vx: float
    vy: float
    r: float
    kind: str
    angle: float = 0.0
    spin: float = 0.0  # deg/s

    def step(self, dt: float) -> None:
        self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt

    def gone(self, height: float) -> bool:
        return self.vy > 0 and self.y - self.r > height


def segment_hits_circle(p: tuple[float, float], q: tuple[float, float],
                        c: tuple[float, float], r: float) -> bool:
    """True if the line segment p-q passes within r of point c."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((c[0] - p[0]) * dx + (c[1] - p[1]) * dy) / length2))
    nx, ny = p[0] + t * dx - c[0], p[1] + t * dy - c[1]
    return nx * nx + ny * ny <= r * r


def launch(rng: random.Random, width: float, height: float, kind: str, r: float) -> Body:
    """Throw a body up from below the screen so it peaks in the upper part and drifts toward the middle."""
    x = rng.uniform(0.15 * width, 0.85 * width)
    y = height + r
    peak = rng.uniform(0.12 * height, 0.4 * height)
    vy = -math.sqrt(2 * GRAVITY * (y - peak))
    flight = 2 * -vy / GRAVITY
    vx = (rng.uniform(0.3 * width, 0.7 * width) - x) / flight
    return Body(x, y, vx, vy, r, kind, 0.0, rng.uniform(-120, 120))


def cam_to_screen(tip: tuple[float, float], cam_size: tuple[int, int],
                  screen_size: tuple[int, int]) -> tuple[float, float]:
    """Map a normalized camera point to the screen, matching the centre crop used for the background."""
    cw, ch = cam_size
    sw, sh = screen_size
    crop_h = min(ch, cw * sh / sw)
    y0 = (ch - crop_h) / 2
    return tip[0] * sw, (tip[1] * ch - y0) / crop_h * sh


@dataclass
class Round:
    duration: float = 60.0
    lives: int = 3
    score: int = 0
    elapsed: float = 0.0

    def tick(self, dt: float) -> None:
        self.elapsed += dt

    @property
    def time_left(self) -> float:
        return max(0.0, self.duration - self.elapsed)

    @property
    def over(self) -> bool:
        return self.lives <= 0 or self.time_left <= 0

    def slice(self, kind: str) -> None:
        if kind == "bomb":
            self.lives -= 1
        else:
            self.score += 1

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def spawn_interval(self) -> float:
        """Seconds between waves: gets faster as the round goes on."""
        return 1.3 - 0.75 * self.progress

    @property
    def bomb_chance(self) -> float:
        return 0.12 + 0.13 * self.progress
