"""Camera capture tests — rotation, config mapping, envelope (Story 1.3).

All hardware/cv2 read paths are mocked so these run without a camera.
"""

import importlib.util
import json
import pathlib

import numpy as np
import pytest

from dum_e import camera
from dum_e.camera import CamConfig, CameraError


# ---- rotation ---------------------------------------------------------------

def test_rotate_frame_dims_for_each_angle():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    assert camera._rotate_frame(frame, 0).shape == (1080, 1920, 3)
    assert camera._rotate_frame(frame, 90).shape == (1920, 1080, 3)   # portrait
    assert camera._rotate_frame(frame, 180).shape == (1080, 1920, 3)
    assert camera._rotate_frame(frame, 270).shape == (1920, 1080, 3)


def test_rotate_90_is_counterclockwise():
    # Mark the top-left pixel; a 90° CCW rotation sends it to the bottom-left.
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    frame[0, 0] = [1, 2, 3]
    out = camera._rotate_frame(frame, 90)
    assert tuple(out[-1, 0]) == (1, 2, 3)


# ---- CamConfig.from_config --------------------------------------------------

def test_from_config_reads_camera_block():
    cfg = {"camera_index": 2, "camera": {"width": 1920, "height": 1080, "rotate": 90, "gain": 64}}
    cam = CamConfig.from_config(cfg)
    assert (cam.index, cam.width, cam.height, cam.rotate, cam.gain) == (2, 1920, 1080, 90, 64)


def test_from_config_defaults_on_empty():
    cam = CamConfig.from_config({})
    assert cam.index == 0 and cam.rotate == 0


def test_invalid_rotate_raises():
    with pytest.raises(CameraError):
        CamConfig(rotate=45)


# ---- capture_frame ----------------------------------------------------------

class _FakeCap:
    def __init__(self, frame):
        self._frame = frame
    def read(self):
        return (self._frame is not None), self._frame
    def release(self):
        pass


def test_capture_frame_applies_rotation_and_reports_wh(tmp_path, monkeypatch):
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(camera, "open_capture", lambda cfg: _FakeCap(frame))
    import cv2
    written = {}
    monkeypatch.setattr(cv2, "imwrite", lambda p, f: written.update(path=p, shape=f.shape) or True)

    out = camera.capture_frame(str(tmp_path / "f.png"), CamConfig(rotate=90))

    assert out["frame_wh"] == [1080, 1920]          # portrait after 90° CCW
    assert written["shape"] == (1920, 1080, 3)       # rotated buffer is what's saved


def test_capture_frame_read_failure_maps_to_e_no_camera(monkeypatch):
    monkeypatch.setattr(camera, "open_capture", lambda cfg: _FakeCap(None))
    with pytest.raises(CameraError) as ei:
        camera.capture_frame("x.png", CamConfig())
    assert ei.value.code == "E_NO_CAMERA"


# ---- survey.py envelope (AC 2) ----------------------------------------------

def _load_survey():
    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("survey_cli", root / "scripts" / "survey.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_survey_capture_emits_envelope(tmp_path, monkeypatch, capsys):
    survey = _load_survey()
    monkeypatch.setattr(survey.config, "load_config", lambda p=None: {"camera": {"rotate": 90}})
    monkeypatch.setattr(survey.rundir, "new_run_dir", lambda *a, **k: str(tmp_path / "run"))
    monkeypatch.setattr(survey, "capture_frame", lambda out, cam: {"path": out, "frame_wh": [1080, 1920]})

    rc = survey.main(["--mode", "capture", "--episode-id", "survey", "--step", "0"])

    env = json.loads(capsys.readouterr().out)
    assert rc == 0 and env["ok"] is True
    assert env["data"]["frame_wh"] == [1080, 1920]
    assert env["data"]["rotate"] == 90
    assert env["artifacts"][0].endswith("frames/survey_0000.png")
