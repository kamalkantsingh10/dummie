"""Camera capture + clip recording (Logitech C920 / UVC).

Dum-E opens the camera as the SOLE owner and locks exposure itself, so GUI
camera apps (Cheese, GNOME Camera) and their auto-exposure are irrelevant to
Dum-E's footage.

GOTCHA (verified on the C920): changing the capture format/resolution RESETS
UVC exposure controls — so anti-flicker controls are applied *after* the format
is configured and the stream has started. Heavy deps (cv2) are imported lazily.

Capture-still is Story 1.3; the clip recorder is Story 3.3 (added early here to
validate the camera end-to-end).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


class CameraError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class CamConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    exposure: int = 200            # 200=20ms (50Hz mains); 167=16.6ms (60Hz)
    power_line_frequency: int = 1  # 1=50Hz, 2=60Hz
    gain: int | None = None

    @property
    def device(self) -> str:
        return f"/dev/video{self.index}"


def _v4l2_set(device: str, ctrl: str, value) -> None:
    subprocess.run(
        ["v4l2-ctl", "-d", device, f"--set-ctrl={ctrl}={value}"],
        check=False,
        capture_output=True,
    )


def apply_anti_flicker(cfg: CamConfig) -> None:
    """Lock manual exposure + power-line frequency. MUST run AFTER the format
    is set (format change resets UVC exposure)."""
    _v4l2_set(cfg.device, "power_line_frequency", cfg.power_line_frequency)
    _v4l2_set(cfg.device, "auto_exposure", 1)  # 1 = Manual Mode
    _v4l2_set(cfg.device, "exposure_time_absolute", cfg.exposure)
    if cfg.gain is not None:
        _v4l2_set(cfg.device, "gain", cfg.gain)


def open_capture(cfg: CamConfig):
    """Open the camera, set MJPG format, start the stream, then lock exposure."""
    import cv2

    cap = cv2.VideoCapture(cfg.index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise CameraError("E_NO_CAMERA", f"could not open {cfg.device} (is it free / connected?)")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.fps)
    # Warm up: read a few frames so the format/stream is live before locking exposure.
    for _ in range(5):
        cap.read()
        time.sleep(0.02)
    apply_anti_flicker(cfg)
    return cap


def capture_frame(out_path: str, cfg: CamConfig | None = None) -> dict:
    """Grab one still to ``out_path``. Returns {path, frame_wh}."""
    import cv2

    cfg = cfg or CamConfig()
    cap = open_capture(cfg)
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise CameraError("E_NO_CAMERA", "frame read failed")
        cv2.imwrite(out_path, frame)
        h, w = frame.shape[:2]
        return {"path": out_path, "frame_wh": [int(w), int(h)]}
    finally:
        cap.release()


def record_clip(out_path: str, seconds: float = 5.0, cfg: CamConfig | None = None) -> dict:
    """Record a clip to ``out_path`` (mp4). Returns {path, frame_wh, frames, mean_luma}.

    ``mean_luma`` is the per-frame mean brightness series — its spread is an
    objective flicker metric (steady brightness => no flicker)."""
    import cv2
    import numpy as np

    cfg = cfg or CamConfig()
    cap = open_capture(cfg)
    writer = None
    luma: list[float] = []
    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, cfg.fps, (cfg.width, cfg.height))
        deadline = time.monotonic() + seconds
        wh = None
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            if wh is None:
                h, w = frame.shape[:2]
                wh = [int(w), int(h)]
            writer.write(frame)
            luma.append(float(np.asarray(frame).mean()))
        if wh is None:
            raise CameraError("E_NO_CAMERA", "no frames captured")
        return {"path": out_path, "frame_wh": wh, "frames": len(luma), "mean_luma": luma}
    finally:
        if writer is not None:
            writer.release()
        cap.release()
