"""Webcam + MediaPipe Hands on a background thread, so the game loop never waits for the camera."""

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
        self.ok = self.cap.isOpened()
        self.frame: np.ndarray | None = None        # latest mirrored RGB frame
        self.tip: tuple[float, float] | None = None  # normalized fingertip, None when no hand
        self.tip_time = 0.0
        self.seq = 0                                # increments on every processed frame
        self._lock = threading.Lock()
        self._running = self.ok
        self._thread = threading.Thread(target=self._loop, daemon=True)
        if self.ok:
            self._thread.start()

    def _loop(self) -> None:
        with mp.solutions.hands.Hands(max_num_hands=1, model_complexity=0,
                                      min_detection_confidence=0.6, min_tracking_confidence=0.5) as hands:
            while self._running:
                ok, bgr = self.cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                rgb = cv2.cvtColor(cv2.flip(bgr, 1), cv2.COLOR_BGR2RGB)  # mirror: moving right moves right
                result = hands.process(rgb)
                tip = None
                if result.multi_hand_landmarks:
                    lm = result.multi_hand_landmarks[0].landmark[INDEX_TIP]
                    tip = (lm.x, lm.y)
                with self._lock:
                    self.frame, self.tip, self.tip_time = rgb, tip, time.perf_counter()
                    self.seq += 1

    def read(self) -> tuple[np.ndarray | None, tuple[float, float] | None, float, int]:
        with self._lock:
            return self.frame, self.tip, self.tip_time, self.seq

    def close(self) -> None:
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        self.cap.release()
