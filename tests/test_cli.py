"""Tests for the frozen script I/O envelope (dum_e.cli)."""

import io
import json

from dum_e import cli


def test_envelope_success_shape():
    env = cli.envelope(True, data={"frame_wh": [640, 480]}, artifacts=["frames/x.png"])
    assert env == {
        "ok": True,
        "data": {"frame_wh": [640, 480]},
        "error": None,
        "artifacts": ["frames/x.png"],
    }


def test_envelope_failure_shape():
    env = cli.envelope(False, error={"code": cli.E_NO_CAMERA, "message": "no cam"})
    assert env["ok"] is False
    assert env["data"] == {}
    assert env["error"] == {"code": "E_NO_CAMERA", "message": "no cam"}
    assert env["artifacts"] == []


def test_ok_writes_single_json_object_and_returns_zero():
    buf = io.StringIO()
    rc = cli.ok(data={"a": 1}, stream=buf)
    assert rc == 0
    parsed = json.loads(buf.getvalue())  # must be exactly one JSON object
    assert parsed["ok"] is True
    assert parsed["data"] == {"a": 1}


def test_fail_writes_error_envelope_and_returns_one():
    buf = io.StringIO()
    rc = cli.fail(cli.E_OUT_OF_BOUNDS, "clamped", stream=buf)
    assert rc == 1
    parsed = json.loads(buf.getvalue())
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "E_OUT_OF_BOUNDS"


def test_error_codes_exist():
    for code in (
        cli.E_NO_CAMERA,
        cli.E_TARGET_NOT_FOUND,
        cli.E_LOST_LOCK,
        cli.E_OUT_OF_BOUNDS,
        cli.E_STOPPED,
        cli.E_CALIB_REQUIRED,
    ):
        assert isinstance(code, str) and code.startswith("E_")
