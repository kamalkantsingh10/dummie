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
        self.engaged = []                      # sids torque-enabled via hold()
        self.released = []                     # sids torque-disabled via relax()
        self._stop_after = stop_after          # create sentinel after N goal writes
        self._stop_path = stop_path

    def open(self): pass
    def close(self): pass
    def read_steps(self, sid): return self.steps[sid]
    def setup(self, sid, acc, speed): self.setups.append((sid, acc, speed))
    def engage(self, sid): self.engaged.append(sid)
    def release(self, sid): self.released.append(sid)

    # joint-range calibration surface (Story 1.6)
    def set_homing(self, ids=None):
        ids = ids or list(self.steps)
        self.homed = list(ids)
        for sid in ids:                          # firmware re-centres present -> 2048
            self.steps[sid] = 2048
        return {sid: 111 for sid in ids}
    def record_ranges(self, ids=None):
        ids = ids or list(self.steps)
        return ({sid: 1500 for sid in ids}, {sid: 2600 for sid in ids})
    def write_calibration(self, cal_by_id): self.written = dict(cal_by_id)
    def recenter(self, sid, mid_steps):
        shift = arm._CENTER - (round(mid_steps) % arm.STEPS_PER_REV)
        self.steps[sid] = (self.steps[sid] + shift) % arm.STEPS_PER_REV   # frame shift, no motion
        self.recentered = (sid, round(mid_steps))
        return 1234

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
    assert len(bus.goals) == 5                            # 1 goal:=present pin + 4 capped ticks
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
    assert len([g for g in bus.goals if g[0] == 1]) == 5   # 1 pin + 4 ticks
    assert len([g for g in bus.goals if g[0] == 2]) == 5


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
    # The driver is now LeRobot's FeetechMotorsBus (which wraps scservo_sdk).
    # Both the raw SDK and the LeRobot motor bus must stay encapsulated in arm.py.
    markers = ("scservo_sdk", "FeetechMotorsBus", "lerobot.motors.feetech")
    offenders = []
    for py in src.glob("*.py"):
        if py.name == "arm.py":
            continue
        text = py.read_text()
        if any(m in text for m in markers):
            offenders.append(py.name)
    assert offenders == [], f"motor driver imported outside arm.py: {offenders}"


# --- LeRobot-backed _FeetechBus: the raw-steps translation layer -------------

class _FakeLeRobotBus:
    """Stands in for lerobot's FeetechMotorsBus; records every call."""

    def __init__(self, port, motors):
        self.port, self.motors = port, motors
        self.calls = []
        self.baud = None
        self.present = {name: 2048 for name in motors}
        self.homing = {name: 0 for name in motors}

    def connect(self, handshake=True): self.calls.append(("connect", handshake))
    def set_baudrate(self, b): self.baud = b
    def read(self, data, motor, *, normalize=True, num_retry=0):
        self.calls.append(("read", data, motor, normalize))
        return self.homing[motor] if data == "Homing_Offset" else self.present[motor]
    def write(self, data, motor, value, *, normalize=True, num_retry=0):
        self.calls.append(("write", data, motor, value, normalize))
        if data == "Homing_Offset":
            self.homing[motor] = value
    def enable_torque(self, motor=None, num_retry=0): self.calls.append(("enable_torque", motor))
    def disable_torque(self, motor=None, num_retry=0): self.calls.append(("disable_torque", motor))
    def disconnect(self, disable_torque=True): self.calls.append(("disconnect", disable_torque))
    def set_half_turn_homings(self, names): return {n: 100 for n in names}
    def record_ranges_of_motion(self, names):
        return ({n: 1500 for n in names}, {n: 2600 for n in names})
    def write_calibration(self, cal): self.calls.append(("write_calibration", sorted(cal)))


def test_feetech_bus_translates_raw_steps_to_lerobot():
    made = {}
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [1, 6],
                         bus_factory=lambda p, m: made.setdefault("b", _FakeLeRobotBus(p, m)))
    fb.open()
    lb = made["b"]
    assert set(lb.motors) == {"j1", "j6"}                       # id -> "j<sid>" names
    assert all(mo.model == "sts3215" for mo in lb.motors.values())
    assert ("connect", False) in lb.calls                      # presence surfaces on read, not handshake
    assert lb.baud == 1_000_000                                # baud configured explicitly

    assert fb.read_steps(6) == 2048
    assert ("read", "Present_Position", "j6", False) in lb.calls   # RAW, never normalized

    fb.setup(1, 20, 500)
    assert ("write", "Acceleration", "j1", 20, False) in lb.calls
    assert ("write", "Goal_Velocity", "j1", 500, False) in lb.calls
    assert ("enable_torque", "j1") in lb.calls

    fb.write_goal(6, 3000)
    assert ("write", "Goal_Position", "j6", 3000, False) in lb.calls
    fb.engage(6); assert ("enable_torque", "j6") in lb.calls
    fb.release(1); assert ("disable_torque", "j1") in lb.calls

    fb.close()
    assert ("disconnect", False) in lb.calls                   # torque preserved -> arm holds, doesn't fall


def test_feetech_bus_open_failure_is_e_no_motors():
    def boom(port, motors): raise RuntimeError("port busy")
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [1], bus_factory=boom)
    with pytest.raises(arm.ArmError) as e:
        fb.open()
    assert e.value.code == "E_NO_MOTORS"


def test_feetech_bus_read_failure_is_e_no_motors():
    class _Boom(_FakeLeRobotBus):
        def read(self, *a, **k): raise RuntimeError("timeout")
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [1], bus_factory=lambda p, m: _Boom(p, m))
    fb.open()
    with pytest.raises(arm.ArmError) as e:
        fb.read_steps(1)
    assert e.value.code == "E_NO_MOTORS"


# --- hold / relax (Story 1.6 prep: per-joint torque for range calibration) ----

def test_hold_writes_present_pose_then_engages(tmp_path):
    bus = FakeBus({1: 1000, 2: 2048, 3: 3000})
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1, 2, 3)), bus=bus) as a:
        a.hold()
    # goal := present (so no jump on torque-on), THEN engage — for every joint
    assert bus.goals == [(1, 1000), (2, 2048), (3, 3000)]
    assert bus.engaged == [1, 2, 3]


def test_hold_subset_only_touches_those_joints(tmp_path):
    bus = FakeBus({1: 1000, 2: 2048, 3: 3000})
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1, 2, 3)), bus=bus) as a:
        a.hold([2])
    assert bus.goals == [(2, 2048)] and bus.engaged == [2]


def test_relax_all_then_subset(tmp_path):
    bus = FakeBus(_center([1, 2, 3]))
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1, 2, 3)), bus=bus) as a:
        a.relax([3])     # free one joint (e.g. to hand-sweep its range)
        a.relax()        # power everything down
    assert bus.released == [3, 1, 2, 3]


def test_hold_relax_reject_unknown_motor_id(tmp_path):
    bus = FakeBus(_center([1]))
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1,)), bus=bus) as a:
        with pytest.raises(arm.ArmError):
            a.hold([9])
        with pytest.raises(arm.ArmError):
            a.relax([9])


# --- joint-range calibration: Arm delegates to LeRobot's facility ------------

def test_home_releases_torque_then_rezeros(tmp_path):
    bus = FakeBus({1: 900, 2: 3500})
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1, 2)), bus=bus) as a:
        homed = a.home()
    assert bus.released == [1, 2]                     # torque off BEFORE changing homing
    assert bus.homed == [1, 2]
    # firmware now reports ~centre (2048) -> ~0 deg after re-zero
    assert all(abs(h["deg_after"]) < 0.2 for h in homed)
    assert homed[0] == {"motor_id": 1, "homing_offset": 111, "deg_after": homed[0]["deg_after"]}


def test_record_ranges_returns_steps_and_degrees(tmp_path):
    bus = FakeBus({1: 2048})
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1,)), bus=bus) as a:
        ranges = a.record_ranges()
    r = ranges[0]
    assert r["motor_id"] == 1 and r["min_steps"] == 1500 and r["max_steps"] == 2600
    assert r["min_deg"] == pytest.approx(arm.steps_to_deg(1500), abs=0.1)
    assert r["max_deg"] == pytest.approx(arm.steps_to_deg(2600), abs=0.1)


def test_recenter_shifts_frame_motion_free(tmp_path):
    bus = FakeBus({1: 1764})                         # midpoint reading 1764 -> should become centre
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1,)), bus=bus) as a:
        off = a.recenter(1, 1764)
    assert off == 1234
    assert bus.recentered == (1, 1764)
    assert bus.steps[1] == arm._CENTER               # frame shifted so midpoint reads centre; verify passed
    assert bus.goals == []                           # NO motion commanded


def test_recenter_rejects_unknown_motor(tmp_path):
    bus = FakeBus({1: 2048})
    with arm.Arm(cfg=_cfg(tmp_path, ids=(1,)), bus=bus) as a:
        with pytest.raises(arm.ArmError):
            a.recenter(9, 2048)


def test_feetech_bus_recenter_writes_in_range_homing_offset():
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [3],
                         bus_factory=lambda p, m: _FakeLeRobotBus(p, m))
    fb.open()
    fb._bus.homing["j3"] = 100                        # current offset
    # midpoint reading 1764 -> centre: shift=2048-1764=284; new offset = 100-284 = -184
    new = fb.recenter(3, 1764)
    assert new == -184 and fb._bus.homing["j3"] == -184


def test_feetech_bus_recenter_reduces_saturated_offset_mod_turn():
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [3],
                         bus_factory=lambda p, m: _FakeLeRobotBus(p, m))
    fb.open()
    fb._bus.homing["j3"] = -2046                      # near the -2047 register limit
    new = fb.recenter(3, 1764)                        # ideal -2330 -> wrapped into range
    assert -2048 <= new <= 2047                       # representable
    assert new == 1766                                # -2330 + 4096


def test_feetech_bus_calibration_maps_ids_to_names():
    made = {}
    fb = arm._FeetechBus("/dev/ttyUSB0", 1_000_000, [1, 6],
                         bus_factory=lambda p, m: made.setdefault("b", _FakeLeRobotBus(p, m)))
    fb.open()
    assert fb.set_homing([6]) == {6: 100}                       # name "j6" -> id 6
    mins, maxes = fb.record_ranges([1, 6])
    assert mins == {1: 1500, 6: 1500} and maxes == {1: 2600, 6: 2600}
    fb.write_calibration({1: {"homing_offset": 0, "range_min": 1500, "range_max": 2600}})
    assert ("write_calibration", ["j1"]) in made["b"].calls
