"""Highest-value safety test: clamping, velocity-cap subdivision, stop-sentinel
halt — all with a MOCKED bus (no hardware, no scservo_sdk needed)."""

import pathlib

import pytest

from dum_e import arm, safety


# --- a fake driver implementing the _FeetechBus surface ----------------------

class FakeBus:
    def __init__(self, start_steps, *, stop_after=None, stop_path=None):
        self.steps = dict(start_steps)         # sid -> steps
        self.goals = []                        # (sid, steps) in command order
        self.setups = []
        self._stop_after = stop_after          # create sentinel after N goal writes
        self._stop_path = stop_path

    def open(self): pass
    def close(self): pass
    def read_steps(self, sid): return self.steps[sid]
    def setup(self, sid, acc, speed): self.setups.append((sid, acc, speed))

    def write_goal(self, sid, steps):
        self.goals.append((sid, steps))
        self.steps[sid] = steps                # pretend the joint reaches instantly
        if self._stop_after is not None and len(self.goals) >= self._stop_after:
            pathlib.Path(self._stop_path).write_text("stop\n")
            self._stop_after = None            # fire once


def _cfg(tmp_path, *, ids=(1,), limits=None, cap=5.0):
    limits = limits or [[-180, 180]] * len(ids)
    return {
        "arm": {"motor_ids": list(ids)},
        "safety": {
            "stop_sentinel": str(tmp_path / "STOP"),
            "joint_limits_deg": limits,
            "velocity_cap_deg_per_step": cap,
        },
    }


def _center(ids):
    return {sid: arm._CENTER for sid in ids}     # all joints at 0°


# --- conversions -------------------------------------------------------------

def test_deg_step_roundtrip_centered():
    assert arm.steps_to_deg(2048) == 0.0
    assert arm.deg_to_steps(0) == 2048
    assert arm.steps_to_deg(arm.deg_to_steps(45)) == pytest.approx(45, abs=0.1)
    assert arm.deg_to_steps(0) == 2048 and arm.steps_to_deg(0) == pytest.approx(-180, abs=0.1)


# --- velocity cap ------------------------------------------------------------

def test_velocity_cap_subdivides_move(tmp_path):
    bus = FakeBus(_center([1]))
    res = arm.move_to([20.0], cfg=_cfg(tmp_path, cap=5.0), bus=bus, tick_s=0)
    assert res["ok"] and res["increments"] == 4          # 20° / 5°-cap = 4 ticks
    assert len(bus.goals) == 4
    # no single tick exceeds the cap (allow <1 encoder-step of quantization)
    prev = 0.0
    for _, steps in bus.goals:
        d = arm.steps_to_deg(steps)
        assert abs(d - prev) <= 5.0 + arm._DEG_PER_STEP
        prev = d
    assert arm.steps_to_deg(bus.goals[-1][1]) == pytest.approx(20.0, abs=0.2)


def test_no_move_when_already_at_target(tmp_path):
    bus = FakeBus(_center([1]))
    res = arm.move_to([0.0], cfg=_cfg(tmp_path), bus=bus, tick_s=0)
    assert res["ok"] and res["increments"] == 0 and bus.goals == []


# --- clamping ----------------------------------------------------------------

def test_target_above_limit_is_clamped(tmp_path):
    bus = FakeBus(_center([1]))
    res = arm.move_to([45.0], cfg=_cfg(tmp_path, limits=[[-10, 10]]), bus=bus, tick_s=0)
    assert res["ok"] and res["clamped"] and "E_OUT_OF_BOUNDS" in res["warnings"]
    assert arm.steps_to_deg(bus.goals[-1][1]) == pytest.approx(10.0, abs=0.2)


def test_target_below_limit_is_clamped(tmp_path):
    bus = FakeBus(_center([1]))
    res = arm.move_to([-45.0], cfg=_cfg(tmp_path, limits=[[-10, 10]]), bus=bus, tick_s=0)
    assert res["clamped"]
    assert arm.steps_to_deg(bus.goals[-1][1]) == pytest.approx(-10.0, abs=0.2)


# --- stop sentinel -----------------------------------------------------------

def test_stop_present_refuses_motion(tmp_path):
    cfg = _cfg(tmp_path)
    safety.request_stop(path=cfg["safety"]["stop_sentinel"])
    bus = FakeBus(_center([1]))
    res = arm.move_to([20.0], cfg=cfg, bus=bus, tick_s=0)
    assert not res["ok"] and res["stopped"]
    assert res["error"]["code"] == "E_STOPPED"
    assert bus.goals == []                                # nothing commanded


def test_stop_midmove_halts_immediately(tmp_path):
    cfg = _cfg(tmp_path, cap=2.0)                          # 20° -> 10 ticks
    sp = cfg["safety"]["stop_sentinel"]
    bus = FakeBus(_center([1]), stop_after=3, stop_path=sp)  # sentinel after 3 goals
    res = arm.move_to([20.0], cfg=cfg, bus=bus, tick_s=0)
    assert not res["ok"] and res["error"]["code"] == "E_STOPPED"
    assert len(bus.goals) == 3                             # halted, no further ticks


# --- relative step + arity ---------------------------------------------------

def test_step_is_relative(tmp_path):
    bus = FakeBus(_center([1]))
    res = arm.step([10.0], cfg=_cfg(tmp_path, cap=5.0), bus=bus, tick_s=0)
    assert res["ok"] and res["increments"] == 2
    assert arm.steps_to_deg(bus.goals[-1][1]) == pytest.approx(10.0, abs=0.2)


def test_wrong_target_count_raises(tmp_path):
    bus = FakeBus(_center([1, 2]))
    with pytest.raises(arm.ArmError):
        arm.move_to([1.0], cfg=_cfg(tmp_path, ids=(1, 2)), bus=bus, tick_s=0)


# --- multi-joint clamp + cap together ---------------------------------------

def test_multijoint_cap_uses_largest_delta(tmp_path):
    bus = FakeBus(_center([1, 2]))
    # joint1 wants +5 (1 tick), joint2 wants +20 (4 ticks) -> 4 ticks total
    res = arm.move_to([5.0, 20.0], cfg=_cfg(tmp_path, ids=(1, 2), cap=5.0), bus=bus, tick_s=0)
    assert res["ok"] and res["increments"] == 4
    assert len([g for g in bus.goals if g[0] == 1]) == 4
    assert len([g for g in bus.goals if g[0] == 2]) == 4


# --- safety module units -----------------------------------------------------

def test_sentinel_set_check_clear(tmp_path):
    p = str(tmp_path / "STOP")
    assert not safety.stop_requested(path=p)
    safety.request_stop(path=p)
    assert safety.stop_requested(path=p)
    safety.clear_stop(path=p)
    assert not safety.stop_requested(path=p)
    safety.clear_stop(path=p)            # idempotent


def test_clamp_to_limits_helper():
    vals, flags = safety.clamp_to_limits([5, -20, 100], [[-10, 10], [-10, 10], None])
    assert vals == [5, -10, 100]
    assert flags == [False, True, False]


# --- architecture guard: arm.py is the ONLY library file touching the driver -

def test_only_arm_imports_motor_driver():
    src = pathlib.Path(arm.__file__).parent
    offenders = []
    for py in src.glob("*.py"):
        if py.name == "arm.py":
            continue
        if "scservo_sdk" in py.read_text():
            offenders.append(py.name)
    assert offenders == [], f"motor driver imported outside arm.py: {offenders}"
