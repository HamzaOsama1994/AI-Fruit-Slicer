"""Webcam + MediaPipe Hands on background threads, so the game loop never waits for the camera."""

from __future__ import annotations

import threading
import time

import cv2
import mediapipe as mp
import numpy as np

INDEX_TIP = 8  # MediaPipe hand landmark: index fingertip


class HandTracker:
    def __init__(self, camera_index: int = 0):
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # DSHOW opens much faster on Windows
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ok = self.cap.isOpened()
        self.frame: np.ndarray | None = None        # latest mirrored RGB frame
        self.tip: tuple[float, float] | None = None  # normalized fingertip, None when no hand
        self.tip_time = 0.0                          # when that frame was captured
        self.seq = 0                                # increments on every processed frame
        self._lock = threading.Lock()
        self._latest: tuple[np.ndarray, float] | None = None
        self._new = threading.Event()
        self._running = self.ok
        # Two threads: one only grabs frames, one runs MediaPipe on the newest. With a single thread,
        # frames queue up while MediaPipe works and the blade trails behind the real finger.
        self._threads = [threading.Thread(target=self._grab_loop, daemon=True),
                         threading.Thread(target=self._loop, daemon=True)]
        if self.ok:
            for t in self._threads:
                t.start()

    def _grab_loop(self) -> None:
        while self._running:
            ok, bgr = self.cap.read()
            if ok:
                with self._lock:
                    self._latest = (bgr, time.perf_counter())
                self._new.set()
            else:
                time.sleep(0.01)

    def _loop(self) -> None:
        with mp.solutions.hands.Hands(max_num_hands=1, model_complexity=0,
                                      min_detection_confidence=0.6, min_tracking_confidence=0.5) as hands:
            while self._running:
                if not self._new.wait(0.1):
                    continue
                self._new.clear()
                with self._lock:
                    bgr, captured = self._latest
                rgb = cv2.cvtColor(cv2.flip(bgr, 1), cv2.COLOR_BGR2RGB)  # mirror: moving right moves right
                result = hands.process(rgb)
                tip = None
                if result.multi_hand_landmarks:
                    lm = result.multi_hand_landmarks[0].landmark[INDEX_TIP]
                    tip = (lm.x, lm.y)
                with self._lock:
                    self.frame, self.tip, self.tip_time = rgb, tip, captured
                    self.seq += 1

    def read(self) -> tuple[np.ndarray | None, tuple[float, float] | None, float, int]:
        with self._lock:
            return self.frame, self.tip, self.tip_time, self.seq

    def close(self) -> None:
        self._running = False
        for t in self._threads:
            if t.is_alive():
                t.join(timeout=1)
        self.cap.release()
