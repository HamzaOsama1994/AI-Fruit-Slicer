from __future__ import annotations

import random

import pytest

from fruit_slicer.logic import Round, cam_to_screen, launch, segment_hits_circle


def test_segment_through_circle_hits():
    assert segment_hits_circle((0, 0), (100, 0), (50, 5), 10)


def test_segment_passing_wide_misses():
    assert not segment_hits_circle((0, 0), (100, 0), (50, 30), 10)


def test_segment_ending_before_circle_misses():
    assert not segment_hits_circle((0, 0), (20, 0), (50, 0), 10)


def test_zero_length_segment_inside_hits():
    assert segment_hits_circle((50, 0), (50, 0), (52, 0), 10)


@pytest.mark.parametrize("seed", range(20))
def test_launch_peaks_on_screen(seed):
    w, h = 1280, 720
    body = launch(random.Random(seed), w, h, "apple", 40)
    top = body.y
    while not body.gone(h):
        body.step(1 / 240)
        top = min(top, body.y)
        assert -body.r < body.x < w + body.r
    assert 0.1 * h < top < 0.42 * h


def test_cam_to_screen_crops_4_3_to_16_9():
    assert cam_to_screen((0.5, 0.5), (640, 480), (1280, 720)) == (640, 360)
    # 4:3 -> 16:9 keeps the middle 360 of 480 rows, so y=60/480 is the top edge
    assert cam_to_screen((0.0, 60 / 480), (640, 480), (1280, 720)) == (0, 0)


def test_round_rules():
    r = Round(duration=60, lives=3)
    r.slice("apple")
    r.slice("bomb")
    assert (r.score, r.lives, r.over) == (1, 2, False)
    r.slice("bomb")
    r.slice("bomb")
    assert r.over


def test_round_ends_on_time_and_speeds_up():
    r = Round(duration=60)
    start = r.spawn_interval
    r.tick(59)
    assert not r.over and r.spawn_interval < start
    r.tick(2)
    assert r.over and r.time_left == 0


def test_one_euro_smooths_jitter_when_still():
    from fruit_slicer.logic import OneEuro
    f, rng = OneEuro(), random.Random(0)
    out = [f((500 + rng.uniform(-6, 6), 300 + rng.uniform(-6, 6)), i / 30) for i in range(60)]
    xs = [p[0] for p in out[30:]]
    assert max(xs) - min(xs) < 6  # raw jitter spans ~12 px


def test_one_euro_keeps_up_with_a_fast_swipe():
    from fruit_slicer.logic import OneEuro
    f = OneEuro()
    for i in range(10):
        x = f((100 + i * 60, 300), i / 30)  # 1800 px/s swipe
    assert x[0] > 100 + 9 * 60 - 30  # less than one camera frame behind


def test_one_euro_reset_jumps_to_new_position():
    from fruit_slicer.logic import OneEuro
    f = OneEuro()
    f((0, 0), 0.0)
    f.reset()
    assert f((900, 500), 0.1) == (900, 500)
