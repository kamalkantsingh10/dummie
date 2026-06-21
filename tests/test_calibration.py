"""Calibration tests (Story 1.6) — pure fits + mocked-frame hand-eye, no hardware."""

import json

import pytest

from dum_e import calibration as cal, cli, safety


def test_unwrap_no_wrap():
    assert cal.unwrap_steps([2000, 2010, 2020, 2015]) == [2000, 2010, 2020, 2015]


def test_unwrap_wrap_up_across_zero():
    # 4090 -> 4095 -> 2 -> 8 : the 4095->2 step is a rollover, not a -4093 move
    cont = cal.unwrap_steps([4090, 4095, 2, 8])
    assert cont == [4090, 4095, 4098, 4104]


def test_unwrap_wrap_down_across_zero():
    cont = cal.unwrap_steps([10, 2, 4090, 4080])
    assert cont == [10, 2, -6, -16]


def test_analyze_detects_wrap_and_true_travel():
    a = cal.analyze_sweep([4090, 4095, 2, 8], motor_id=4)
    assert a["wrapped"] is True
    assert a["wrap_crossings"] == 1
    assert a["raw_min"] == 2 and a["raw_max"] == 4095   # raw min/max are misleading
    assert a["travel_steps"] == 14                       # true contiguous travel
    assert a["motor_id"] == 4


def test_analyze_no_wrap_uses_raw_range():
    a = cal.analyze_sweep(list(range(2000, 2301, 10)), motor_id=1)
    assert a["wrapped"] is False
    assert a["raw_min"] == 2000 and a["raw_max"] == 2300
    assert a["travel_steps"] == 300
    assert a["travel_deg"] == round(300 * 360 / 4096, 1)


def test_analyze_empty():
    assert cal.analyze_sweep([], motor_id=2)["n_samples"] == 0


def test_load_and_summarize_roundtrip(tmp_path):
    p = tmp_path / "sweep.jsonl"
    lines = [{"meta": {"motor_ids": [5, 6], "hz": 50}}]
    # joint 5 sweeps cleanly; joint 6 wraps across zero
    j5 = [1800, 1850, 1900, 1950]
    j6 = [4080, 4095, 5, 20]
    rows = [[round(i * 0.02, 3), j5[i], j6[i]] for i in range(4)]
    p.write_text("\n".join(json.dumps(x) for x in (lines + rows)) + "\n")

    loaded = cal.load_sweep(str(p))
    assert loaded["motor_ids"] == [5, 6]
    assert loaded["samples"][0] == j5 and loaded["samples"][1] == j6

    summ = cal.summarize_sweeps(loaded)
    assert summ[0]["motor_id"] == 5 and summ[0]["wrapped"] is False
    assert summ[1]["motor_id"] == 6 and summ[1]["wrapped"] is True


# --- Part 2: hand-eye image-Jacobian -----------------------------------------

def test_fit_axis_perfect_linear():
    m, r2 = cal.fit_axis([-2, -1, 1, 2], [-20, -10, 10, 20])  # 10 px/deg, clean
    assert m == pytest.approx(10.0)
    assert r2 == pytest.approx(1.0)


def test_fit_axis_no_motion_is_zero_gain_zero_r2():
    m, r2 = cal.fit_axis([-2, -1, 1, 2], [0.0, 0.0, 0.0, 0.0])
    assert m == 0.0 and r2 == 0.0


def test_fit_axis_noise_lowers_r2():
    _, r2 = cal.fit_axis([-2, -1, 1, 2], [-20, 11, -9, 21])  # one sign-flipped point
    assert r2 < 0.9


def test_fit_joint_picks_dominant_axis():
    # shifts mostly in y => primary axis y
    jf = cal.fit_joint(3, [-2, -1, 1, 2], [(0.1, -16), (0.0, -8), (-0.1, 8), (0.0, 16)])
    assert jf["primary_axis"] == "y"
    assert jf["gain"] == pytest.approx(8.0, abs=0.1)
    assert jf["motor_id"] == 3


def test_assemble_profile_ok_needs_both_axes():
    fits = [
        cal.fit_joint(1, [-1, 1], [(-10, 0), (10, 0)]),   # strong x
        cal.fit_joint(4, [-1, 1], [(0, -9), (0, 9)]),     # strong y
        cal.fit_joint(5, [-1, 1], [(0.1, 0.1), (-0.1, -0.1)]),  # negligible
    ]
    prof = cal.assemble_profile(fits, frame_wh=[640, 480], deltas_deg=[-1, 1], created="T")
    assert prof["ok"] is True
    assert prof["axis_coverage"] == {"x": 1, "y": 4}
    assert prof["quality"]["n_usable"] == 2
    assert prof["version"] == cal.HANDEYE_VERSION


def test_assemble_profile_not_ok_when_one_axis_missing():
    fits = [cal.fit_joint(1, [-1, 1], [(-10, 0), (10, 0)])]  # x only, no y
    prof = cal.assemble_profile(fits, frame_wh=[640, 480], deltas_deg=[-1, 1], created="T")
    assert prof["ok"] is False
    assert prof["axis_coverage"]["y"] is None


def test_save_load_roundtrip_and_determinism(tmp_path):
    fits = [cal.fit_joint(1, [-1, 1], [(-10, 0), (10, 0)])]
    prof = cal.assemble_profile(fits, frame_wh=[640, 480], deltas_deg=[-1, 1], created="T")
    p = tmp_path / "handeye.json"
    cal.save_profile(prof, str(p))
    first = p.read_text()
    cal.save_profile(prof, str(p))                 # re-run overwrites deterministically (AC 5)
    assert p.read_text() == first
    assert cal.load_profile(str(p))["axis_coverage"] == prof["axis_coverage"]


def test_load_missing_raises_calib_required(tmp_path):
    with pytest.raises(cal.CalibrationError) as e:
        cal.load_profile(str(tmp_path / "nope.json"))
    assert e.value.code == cli.E_CALIB_REQUIRED


def test_load_version_mismatch_raises_calib_required(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"version": 0, "kind": "handeye_image_jacobian"}))
    with pytest.raises(cal.CalibrationError) as e:
        cal.load_profile(str(p))
    assert e.value.code == cli.E_CALIB_REQUIRED


# --- calibrate() orchestration with a fake arm + mocked frame shifts ----------

class _FakeArm:
    """Tracks a commanded pose; step() routes deltas the way arm.step would."""

    def __init__(self, motor_ids, *, stop_after=None):
        self.motor_ids = list(motor_ids)
        self.pose = [0.0] * len(motor_ids)
        self.calls = []
        self._stop_after = stop_after

    def step(self, deltas, stop_path=None):
        self.calls.append(list(deltas))
        if self._stop_after is not None and len(self.calls) > self._stop_after:
            return {"ok": False, "stopped": True, "error": {"code": "E_STOPPED", "message": "x"}}
        self.pose = [p + d for p, d in zip(self.pose, deltas)]
        return {"ok": True, "stopped": False, "error": None}


def _grab_factory(armobj):
    import numpy as np
    # 4x8 frame; encode the live pose in row 0 so the mocked measure can read it.
    def grab():
        img = np.zeros((4, 8), dtype=float)
        img[0, : len(armobj.pose)] = armobj.pose
        return img
    return grab


def _measure_factory(motor_ids, gains):
    def measure(ref, cur):
        dp = [c - r for r, c in zip(ref[0, : len(motor_ids)], cur[0, : len(motor_ids)])]
        dx = sum(gains.get(m, (0, 0))[0] * dp[i] for i, m in enumerate(motor_ids))
        dy = sum(gains.get(m, (0, 0))[1] * dp[i] for i, m in enumerate(motor_ids))
        return dx, dy, 0.99
    return measure


def test_calibrate_recovers_gains_and_passes():
    ids = [1, 4, 5]
    gains = {1: (10.0, 0.0), 4: (0.0, 8.0), 5: (0.0, 0.0)}  # 1->x, 4->y, 5->none
    a = _FakeArm(ids)
    prof = cal.calibrate(
        a, _grab_factory(a), measure=_measure_factory(ids, gains),
        deltas_deg=(-2.0, -1.0, 1.0, 2.0), settle_s=0, created="T",
    )
    assert prof["ok"] is True
    assert prof["frame_wh"] == [8, 4]
    by_id = {j["motor_id"]: j for j in prof["joints"]}
    assert by_id[1]["px_per_deg"][0] == pytest.approx(10.0)
    assert by_id[4]["px_per_deg"][1] == pytest.approx(8.0)
    assert by_id[5]["usable"] is False
    assert prof["axis_coverage"] == {"x": 1, "y": 4}
    # each joint returns to start (net commanded offset is zero)
    assert a.pose == pytest.approx([0.0, 0.0, 0.0])


def test_calibrate_aborts_on_stop_sentinel(tmp_path):
    stop = tmp_path / "STOP"
    stop.write_text("stop\n")
    ids = [1, 2]
    a = _FakeArm(ids)
    prof = cal.calibrate(
        a, _grab_factory(a), measure=_measure_factory(ids, {}),
        settle_s=0, created="T", stop_path=str(stop),
    )
    assert prof["ok"] is False
    assert prof["error"]["code"] == cli.E_STOPPED
    assert a.calls == []  # refused to move with the sentinel already present


def test_calibrate_aborts_when_step_reports_stopped():
    ids = [1, 2]
    a = _FakeArm(ids, stop_after=1)  # second step returns stopped
    prof = cal.calibrate(
        a, _grab_factory(a), measure=_measure_factory(ids, {1: (10.0, 0.0)}),
        deltas_deg=(-1.0, 1.0), settle_s=0, created="T",
    )
    assert prof["ok"] is False
    assert prof["error"]["code"] == cli.E_STOPPED


# --- joint-range calibration helpers (LeRobot ranges -> soft limits) ----------

def _ranges(*triples):
    # (motor_id, min_deg, max_deg) -> the record_ranges-shaped dicts
    return [{"motor_id": m, "min_deg": lo, "max_deg": hi,
             "min_steps": cal.STEPS_PER_REV // 2 + round(lo / cal._DEG_PER_STEP),
             "max_steps": cal.STEPS_PER_REV // 2 + round(hi / cal._DEG_PER_STEP)}
            for m, lo, hi in triples]


def test_build_joint_limits_orders_and_applies_margin():
    ranges = _ranges((2, -80.0, 80.0), (1, -10.0, 50.0))
    limits = cal.build_joint_limits(ranges, [1, 2], margin_deg=3.0)
    assert limits == [[-7.0, 47.0], [-77.0, 77.0]]   # ordered by motor_ids, shrunk 3deg each side


def test_build_joint_limits_handles_reversed_min_max():
    ranges = _ranges((1, 60.0, -60.0))               # max recorded before min
    assert cal.build_joint_limits(ranges, [1], margin_deg=5.0) == [[-55.0, 55.0]]


def test_build_joint_limits_margin_wider_than_travel_collapses_to_midpoint():
    ranges = _ranges((1, 10.0, 12.0))
    lim = cal.build_joint_limits(ranges, [1], margin_deg=5.0)
    assert lim[0][0] == lim[0][1]                     # degenerate, not inverted


def test_build_calibration_uses_raw_steps_and_offsets():
    ranges = _ranges((1, -90.0, 90.0))
    cal_dict = cal.build_calibration(ranges, {1: 123}, [1])
    assert cal_dict[1]["homing_offset"] == 123
    assert cal_dict[1]["range_min"] < cal_dict[1]["range_max"]
    assert cal_dict[1]["drive_mode"] == 0


def test_limit_from_range_applies_margin_and_collapses():
    assert cal.limit_from_range(-50, 60, margin_deg=3) == [-47.0, 57.0]
    assert cal.limit_from_range(60, -50, margin_deg=3) == [-47.0, 57.0]   # order-insensitive
    lim = cal.limit_from_range(10, 12, margin_deg=5)                       # margin > travel
    assert lim[0] == lim[1]


def test_merge_accumulates_joints_and_is_deterministic(tmp_path):
    p = str(tmp_path / "joints.json")
    cal.merge_joint_result(4, homing_offset=2206, range_min=1418, range_max=2678,
                           limit_deg=[-52.4, 52.4], path=p)
    first = open(p).read()
    cal.merge_joint_result(4, homing_offset=2206, range_min=1418, range_max=2678,
                           limit_deg=[-52.4, 52.4], path=p)   # same write -> identical bytes
    assert open(p).read() == first
    prof = cal.merge_joint_result(2, homing_offset=10, range_min=1000, range_max=3000,
                                  limit_deg=[-70.0, 70.0], path=p)   # second joint accumulates
    assert set(prof["motors"]) == {"2", "4"}
    assert cal.load_joint_calibration(p)["motors"]["4"]["homing_offset"] == 2206


def test_joint_limits_for_fills_defaults_for_uncalibrated(tmp_path):
    p = str(tmp_path / "joints.json")
    prof = cal.merge_joint_result(4, homing_offset=0, range_min=1418, range_max=2678,
                                  limit_deg=[-52.4, 52.4], path=p)
    ordered = cal.joint_limits_for(prof, [1, 2, 3, 4, 5, 6], default=(-180.0, 180.0))
    assert ordered[3] == [-52.4, 52.4]                 # motor 4 calibrated
    assert ordered[0] == [-180.0, 180.0]               # motor 1 still placeholder


def test_load_joint_calibration_missing_or_old_raises(tmp_path):
    with pytest.raises(cal.CalibrationError) as e:
        cal.load_joint_calibration(str(tmp_path / "nope.json"))
    assert e.value.code == cli.E_CALIB_REQUIRED
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"version": 1}))            # pre-v2 format -> recalibrate
    with pytest.raises(cal.CalibrationError) as e:
        cal.load_joint_calibration(str(p))
    assert e.value.code == cli.E_CALIB_REQUIRED
