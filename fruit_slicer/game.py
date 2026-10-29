"""AI Fruit Slicer: slice fruit with your index finger in front of the webcam."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import deque
from pathlib import Path

import pygame

from . import assets
from .logic import MIN_SLICE_SPEED, Body, Round, cam_to_screen, launch, segment_hits_circle
from .tracker import HandTracker

W, H = 1280, 720
TRAIL_SECONDS = 0.15
GOLD, GREEN, ORANGE, RED = (255, 200, 40), (90, 230, 120), (255, 170, 60), (255, 80, 80)
BEST_FILE = Path(__file__).resolve().parent.parent / "best_score.json"


def load_best() -> int:
    try:
        return int(json.loads(BEST_FILE.read_text())["best"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


class Game:
    def __init__(self, camera: int, duration: float, fullscreen: bool):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()  # mixer failing (no audio device) is fine: assets.sounds() falls back to silence
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED | (pygame.FULLSCREEN if fullscreen else 0))
        pygame.display.set_caption("AI Fruit Slicer - قاطع الفواكه الذكي")
        self.clock = pygame.time.Clock()
        self.tracker = HandTracker(camera)
        self.sfx = assets.sounds()
        self.whole = {k: assets.whole(k) for k in assets.FRUITS}
        self.halves = {k: assets.halves(k) for k in assets.FRUITS}
        self.bomb_img = assets.bomb()
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim.fill((10, 10, 25, 120))
        self.backdrop = pygame.Surface((W, H))
        for y in range(H):  # plain gradient when there is no camera image
            pygame.draw.line(self.backdrop, (40 + y // 24, 25 + y // 40, 20), (0, y), (W, y))
        self.bg, self.bg_seq = None, -1
        self.rng = random.Random()
        self.duration = duration
        self.best = load_best()
        self.trail: deque[tuple[float, float, float]] = deque()
        self.last_seq, self.hand_seen, self.tip_screen = -1, -10.0, None
        self.bodies: list[Body] = []
        self.pieces: list[tuple[Body, pygame.Surface]] = []
        self.particles: list[list] = []
        self.popups: list[list] = []
        self.flash = 0.0
        self.round = Round(duration)
        self.new_best = False
        self.to_menu()

    # ── Scenes ────────────────────────────────────────────────────────────────
    def to_menu(self) -> None:
        self.scene, self.target_y = "menu", 430
        self.target = Body(W / 2, self.target_y, 0, 0, assets.FRUITS["watermelon"]["r"], "watermelon")

    def start_round(self) -> None:
        self.scene, self.target = "play", None
        self.round, self.next_wave, self.new_best = Round(self.duration), 0.8, False
        self.bodies.clear()
        self.sfx["start"].play()

    def end_round(self) -> None:
        self.scene, self.over_time, self.target, self.target_y = "over", time.perf_counter(), None, 540
        self.sfx["over"].play()
        if self.round.score > self.best:
            self.best, self.new_best = self.round.score, True
            BEST_FILE.write_text(json.dumps({"best": self.best}))

    # ── Input ─────────────────────────────────────────────────────────────────
    def blade_segments(self, now: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """Add new fingertip (or held-mouse) positions to the trail; return the fast moves that can cut."""
        frame, tip, t, seq = self.tracker.read()
        points = []
        if seq != self.last_seq:
            self.last_seq = seq
            if tip is None:
                self.trail.clear()  # hand lost: never join the old and new positions into one cut
            else:
                self.tip_screen = cam_to_screen(tip, (frame.shape[1], frame.shape[0]), (W, H))
                self.hand_seen = now
                points.append((*self.tip_screen, t))
        if pygame.mouse.get_pressed()[0]:
            points.append((*pygame.mouse.get_pos(), now))
        segments = []
        for x, y, t in points:
            if self.trail:
                px, py, pt = self.trail[-1]
                dt = t - pt
                if 0 < dt < 0.2 and math.hypot(x - px, y - py) / dt >= MIN_SLICE_SPEED:
                    segments.append(((px, py), (x, y)))
            self.trail.append((x, y, t))
        while len(self.trail) > 1 and now - self.trail[0][2] > TRAIL_SECONDS:
            self.trail.popleft()
        return segments

    def cut(self, p, q) -> None:
        if self.target and segment_hits_circle(p, q, (self.target.x, self.target.y), self.target.r * 1.5):
            self.split(self.target, p, q)
            self.start_round()
        elif self.scene == "play":
            for b in [b for b in self.bodies if segment_hits_circle(p, q, (b.x, b.y), b.r)]:
                self.bodies.remove(b)
                self.round.slice(b.kind)
                if b.kind == "bomb":
                    self.explode(b)
                else:
                    self.split(b, p, q)
                    self.popups.append([b.x, b.y, "+1", 0.8])

    # ── Effects ───────────────────────────────────────────────────────────────
    def split(self, b: Body, p, q) -> None:
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length              # halves fly apart across the cut
        base = 90 - math.degrees(math.atan2(dy, dx))    # turn the half-images so the cut line follows the swipe
        for surf, sgn in zip(self.halves[b.kind], (1, -1)):
            piece = Body(b.x + sgn * nx * b.r / 4, b.y + sgn * ny * b.r / 4,
                         b.vx + sgn * nx * 160, b.vy + sgn * ny * 160 - 100, b.r, b.kind,
                         base, sgn * self.rng.uniform(60, 180))
            self.pieces.append((piece, surf))
        self.burst(b.x, b.y, assets.FRUITS[b.kind]["flesh"], 18)
        self.sfx["slice"].play()

    def explode(self, b: Body) -> None:
        self.flash = 1.0
        self.burst(b.x, b.y, ORANGE, 30)
        self.burst(b.x, b.y, (60, 60, 60), 20)
        self.popups.append([b.x, b.y, "-1", 1.0])
        self.sfx["bomb"].play()

    def burst(self, x: float, y: float, color, n: int) -> None:
        for _ in range(n):
            a, s = self.rng.uniform(0, math.tau), self.rng.uniform(100, 450)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, self.rng.uniform(0.3, 0.7),
                                   color, self.rng.randint(3, 7)])

    def spawn_wave(self) -> None:
        for _ in range(1 + self.rng.randint(0, 1 + int(2 * self.round.progress))):
            if self.rng.random() < self.round.bomb_chance:
                kind, r = "bomb", assets.BOMB_R
            else:
                kind = self.rng.choice(list(assets.FRUITS))
                r = assets.FRUITS[kind]["r"]
            self.bodies.append(launch(self.rng, W, H, kind, r))

    # ── Update / draw ─────────────────────────────────────────────────────────
    def update(self, dt: float, now: float) -> None:
        for p, q in self.blade_segments(now):
            self.cut(p, q)
        if self.scene == "play":
            self.round.tick(dt)
            self.next_wave -= dt
            if self.next_wave <= 0:
                self.spawn_wave()
                self.next_wave = self.round.spawn_interval
            if self.round.over:
                self.end_round()
        if self.scene == "over" and self.target is None and now - self.over_time > 1.5:
            self.target = Body(W / 2, self.target_y, 0, 0, assets.FRUITS["watermelon"]["r"], "watermelon")
        if self.target:
            self.target.y = self.target_y + math.sin(now * 2) * 12
            self.target.angle += 30 * dt
        for b in self.bodies:
            b.step(dt)
        for b, _ in self.pieces:
            b.step(dt)
        self.bodies = [b for b in self.bodies if not b.gone(H)]
        self.pieces = [(b, s) for b, s in self.pieces if not b.gone(H)]
        for pt in self.particles:
            pt[3] += 500 * dt
            pt[0] += pt[2] * dt
            pt[1] += pt[3] * dt
            pt[4] -= dt
        self.particles = [pt for pt in self.particles if pt[4] > 0]
        for pp in self.popups:
            pp[1] -= 60 * dt
            pp[3] -= dt
        self.popups = [pp for pp in self.popups if pp[3] > 0]
        self.flash = max(0.0, self.flash - dt * 2.5)

    def draw_background(self) -> None:
        frame, _, _, seq = self.tracker.read()
        if frame is None:
            self.screen.blit(self.backdrop, (0, 0))
            return
        if seq != self.bg_seq:  # rebuild only when the camera has a new frame
            h, w = frame.shape[:2]
            crop_h = int(min(h, w * H / W))
            y0 = (h - crop_h) // 2
            cam = pygame.image.frombuffer(frame[y0:y0 + crop_h].tobytes(), (w, crop_h), "RGB")
            self.bg, self.bg_seq = pygame.transform.smoothscale(cam, (W, H)).convert(), seq
            self.bg.blit(self.dim, (0, 0))  # darken once per camera frame, not every game frame
        self.screen.blit(self.bg, (0, 0))

    def blit_rotated(self, img: pygame.Surface, x: float, y: float, angle: float) -> None:
        rotated = pygame.transform.rotate(img, angle)
        self.screen.blit(rotated, rotated.get_rect(center=(int(x), int(y))))

    def draw(self, now: float) -> None:
        s = self.screen
        self.draw_background()
        for b in self.bodies:
            if b.kind == "bomb":
                self.screen.blit(self.bomb_img, self.bomb_img.get_rect(center=(int(b.x), int(b.y))))
                spark = (int(b.x + 12), int(b.y - b.r - 16))
                pygame.draw.circle(s, (255, 230, 80) if int(now * 12) % 2 else (255, 120, 30), spark, 6)
            else:
                self.blit_rotated(self.whole[b.kind], b.x, b.y, b.angle)
        for b, surf in self.pieces:
            self.blit_rotated(surf, b.x, b.y, b.angle)
        for x, y, _, _, life, color, r in self.particles:
            pygame.draw.circle(s, color, (int(x), int(y)), max(1, int(r * life / 0.7)))
        if self.target:
            self.blit_rotated(self.whole["watermelon"], self.target.x, self.target.y, self.target.angle)
        self.draw_blade(now)
        for x, y, label, life in self.popups:
            assets.text(s, label, 40, (x, y), RED if label.startswith("-") else GOLD)
        {"menu": self.draw_menu, "play": self.draw_hud, "over": self.draw_over}[self.scene]()
        if self.flash > 0:
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((255, 60, 40, int(150 * self.flash)))
            s.blit(overlay, (0, 0))

    def draw_blade(self, now: float) -> None:
        pts = [(x, y) for x, y, _ in self.trail]
        for i in range(1, len(pts)):
            width = 2 + 12 * i // len(pts)
            pygame.draw.line(self.screen, (70, 190, 255), pts[i - 1], pts[i], width + 6)
            pygame.draw.line(self.screen, (255, 255, 255), pts[i - 1], pts[i], width)
        if self.tip_screen and now - self.hand_seen < 0.3:  # show where the finger is, even when still
            pygame.draw.circle(self.screen, (255, 255, 255), [int(v) for v in self.tip_screen], 9, 3)

    def draw_menu(self) -> None:
        s, now = self.screen, time.perf_counter()
        assets.text(s, "AI Fruit Slicer", 84, (W / 2, 95), GOLD)
        assets.text(s, "قاطع الفواكه الذكي", 54, (W / 2, 172), GOLD)
        assets.text(s, "Slice the watermelon with your finger to start", 30, (W / 2, 262))
        assets.text(s, "اقطع البطيخة بإصبعك لتبدأ", 32, (W / 2, 305))
        assets.text(s, "Slice fruit for points  -  avoid the bombs", 26, (W / 2, 550))
        assets.text(s, "اقطع الفواكه وتجنب القنابل", 28, (W / 2, 588))
        if not self.tracker.ok:
            status, color = "No camera found: hold the mouse button and swipe   لم يتم العثور على الكاميرا", RED
        elif now - self.hand_seen < 0.5:
            status, color = "● Hand detected   تم رصد اليد", GREEN
        else:
            status, color = "● Show your hand to the camera   أظهر يدك أمام الكاميرا", ORANGE
        assets.text(s, status, 26, (W / 2, 660), color)
        assets.text(s, f"BEST {self.best}  أفضل نتيجة", 26, (W - 30, 30), GOLD, anchor="topright")

    def draw_hud(self) -> None:
        s, r = self.screen, self.round
        assets.text(s, "SCORE  النقاط", 24, (30, 18), anchor="topleft")
        assets.text(s, str(r.score), 64, (30, 48), GOLD, anchor="topleft")
        left = math.ceil(r.time_left)
        assets.text(s, "TIME  الوقت", 24, (W / 2, 32))
        assets.text(s, f"{left // 60}:{left % 60:02d}", 56, (W / 2, 82), RED if left <= 10 else (255, 255, 255))
        for i in range(3):
            assets.heart(s, (W - 170 + i * 60, 60), 44, i < r.lives)

    def draw_over(self) -> None:
        s, r = self.screen, self.round
        if r.lives <= 0:
            assets.text(s, "GAME OVER", 72, (W / 2, 90), RED)
            assets.text(s, "انتهت اللعبة", 50, (W / 2, 160), RED)
        else:
            assets.text(s, "TIME'S UP!", 72, (W / 2, 90), GOLD)
            assets.text(s, "انتهى الوقت!", 50, (W / 2, 160), GOLD)
        assets.text(s, "SCORE  النقاط", 30, (W / 2, 240))
        assets.text(s, str(r.score), 110, (W / 2, 320), GOLD)
        if self.new_best:
            assets.text(s, "NEW BEST!  رقم قياسي جديد", 34, (W / 2, 410), GREEN)
        else:
            assets.text(s, f"BEST {self.best}  أفضل نتيجة", 30, (W / 2, 410))
        if self.target:
            assets.text(s, "Slice to play again   اقطع للعب مرة أخرى", 30, (W / 2, 640))

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self) -> None:
        while True:
            dt = min(self.clock.tick(60) / 1000, 0.05)  # cap dt so a stall doesn't teleport fruit
            now = time.perf_counter()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.scene != "play":
                    self.start_round()
            self.update(dt, now)
            self.draw(now)
            pygame.display.flip()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Fruit Slicer - gesture controlled fruit slicing game")
    parser.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    parser.add_argument("--duration", type=float, default=60, help="round length in seconds (default 60)")
    parser.add_argument("--fullscreen", action="store_true", help="start fullscreen (toggle with F)")
    args = parser.parse_args()
    game = Game(args.camera, args.duration, args.fullscreen)
    try:
        game.run()
    finally:
        game.tracker.close()
        pygame.quit()


if __name__ == "__main__":
    main()
