"""bringup aggregation tests (Story 1.4) — motor-read + camera mocked, no hardware."""

import importlib.util
import json
import pathlib

import pytest

from dum_e import arm, camera


def _load_bringup():
    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("bringup_cli", root / "scripts" / "bringup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def bringup(monkeypatch, tmp_path):
    mod = _load_bringup()
    # Never touch real config / hardware.
    monkeypatch.setattr(mod.config, "load_config", lambda p=None: {})
    monkeypatch.setattr(mod.rundir, "new_run_dir", lambda *a, **k: str(tmp_path / "run"))
    return mod


def _good_joints(**kw):
    return {
        "joint_pos": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        "raw_steps": [114, 228, 341, 455, 569, 683],
        "motor_ids": [1, 2, 3, 4, 5, 6],
        "joint_units": "deg",
    }


def test_both_ok(bringup, monkeypatch):
    monkeypatch.setattr(bringup.arm, "read_joints", _good_joints)
    monkeypatch.setattr(bringup.camera, "capture_frame",
                        lambda out, cam: {"path": out, "frame_wh": [1080, 1920]})

    rc, env = _run(bringup)

    assert rc == 0 and env["ok"] is True
    assert len(env["data"]["joint_pos"]) == 6
    assert env["data"]["joint_units"] == "deg"
    assert env["data"]["frame_wh"] == [1080, 1920]
    assert env["artifacts"][0].endswith("frames/bringup_0000.png")
    assert env["error"] is None


def _run(mod):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main([])
    return rc, json.loads(buf.getvalue())


def test_motor_failure_is_not_ok(bringup, monkeypatch):
    def boom(*a, **k):
        raise arm.ArmError("E_NO_MOTORS", "motor id 3 did not respond")
    monkeypatch.setattr(bringup.arm, "read_joints", boom)
    monkeypatch.setattr(bringup.camera, "capture_frame",
                        lambda out, cam: {"path": out, "frame_wh": [1080, 1920]})

    rc, env = _run(bringup)
    assert rc == 1 and env["ok"] is False
    assert env["error"]["code"] == "E_NO_MOTORS"
    # camera still ran (independent legs) -> frame present even on motor failure
    assert env["data"]["frame_wh"] == [1080, 1920]


def test_camera_failure_is_not_ok(bringup, monkeypatch):
    monkeypatch.setattr(bringup.arm, "read_joints", _good_joints)
    def boom(*a, **k):
        raise camera.CameraError("E_NO_CAMERA", "could not open /dev/video0")
    monkeypatch.setattr(bringup.camera, "capture_frame", boom)

    rc, env = _run(bringup)
    assert rc == 1 and env["ok"] is False
    assert env["error"]["code"] == "E_NO_CAMERA"
    assert env["data"]["joint_pos"]  # motor leg still reported


def test_both_fail_reports_both(bringup, monkeypatch):
    monkeypatch.setattr(bringup.arm, "read_joints",
                        lambda *a, **k: (_ for _ in ()).throw(arm.ArmError("E_NO_MOTORS", "no bus")))
    monkeypatch.setattr(bringup.camera, "capture_frame",
                        lambda *a, **k: (_ for _ in ()).throw(camera.CameraError("E_NO_CAMERA", "no cam")))
    rc, env = _run(bringup)
    assert rc == 1 and env["ok"] is False
    assert "E_NO_MOTORS" in env["error"]["message"] and "E_NO_CAMERA" in env["error"]["message"]

# (arm step<->deg + bus resolution are now covered in tests/test_arm_safety.py)
