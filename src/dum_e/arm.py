"""Arm control — the SOLE path to the servos (safety chokepoint, FR-14).

NOTHING else in the runtime/library may import the motor driver. Every motion
routes through here and is, on every control tick:
  * clamped to the configured soft joint limits (E_OUT_OF_BOUNDS, logged),
  * capped by the per-step velocity limit (a move is subdivided into <=cap ticks),
  * aborted the instant the stop sentinel appears (E_STOPPED), holding position.

Driver = Feetech STS3215 bus via LeRobot's ``FeetechMotorsBus`` (which wraps
``scservo_sdk``), lazy-imported and fully encapsulated in :class:`_FeetechBus`
so ``import dum_e.arm`` works with no LeRobot/SDK or hardware, and so a
driver/version change touches only this file. We lean on LeRobot for the wire
protocol + torque control (and, in Story 1.6, its joint-range calibration), but
exchange RAW encoder steps (``normalize=False``) so the safety layer's
steps<->deg math and soft limits are unchanged and need no calibration dict.

Units: degrees, CENTERED on the encoder mid-point ->
    deg = (steps - 2048) * 360/4096   in [-180, 180)
This matches ``config.yaml`` ``joint_limits_deg`` and is what Story 1.6 will
re-home. (Until 1.6 sets real limits, the placeholder [-180,180] = full range.)
"""

from __future__ import annotations

import math
import time

from dum_e import cli, config as _config, safety

JOINT_UNITS = "deg"
N_JOINTS = 6
STEPS_PER_REV = 4096               # STS3215: 4096 steps = 360°
_CENTER = STEPS_PER_REV // 2       # 2048 == 0°
_DEG_PER_STEP = 360.0 / STEPS_PER_REV

_DEFAULT_PORT = "/dev/ttyUSB0"
_DEFAULT_BAUD = 1000000
_DEFAULT_IDS = [1, 2, 3, 4, 5, 6]
_DEFAULT_VEL_CAP = 5.0             # deg per control tick
_DEFAULT_TICK_S = 0.12            # dwell per increment (real motion needs time)


class ArmError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def steps_to_deg(steps: int) -> float:
    """Encoder steps -> centered degrees in [-180, 180)."""
    return (steps - _CENTER) * _DEG_PER_STEP


def deg_to_steps(deg: float) -> int:
    """Centered degrees -> encoder steps, clamped to the valid [0, 4095] range."""
    return max(0, min(STEPS_PER_REV - 1, round(deg / _DEG_PER_STEP + _CENTER)))


# --- Driver (the ONLY place the motor SDK is imported) -----------------------

class _FeetechBus:
    """Raw-steps Feetech driver on top of LeRobot's ``FeetechMotorsBus``.

    Keeps a tiny per-motor surface (``read_steps`` / ``setup`` / ``write_goal``
    / ``engage`` / ``release``) so :class:`Arm` above it is unchanged. LeRobot's
    bus is keyed by motor *name*, so we map each motor id ``sid`` to a synthetic
    name ``"j<sid>"``. All position I/O is RAW (``normalize=False``) — 0..4095
    steps — so no calibration dict is needed to drive the arm.

    ``bus_factory(port, motors) -> lerobot bus`` is injectable for unit tests
    (the default builds a real ``FeetechMotorsBus``).
    """

    _MODEL = "sts3215"

    def __init__(self, port: str, baud: int, motor_ids, *, bus_factory=None):
        self.port, self.baud = port, baud
        self.motor_ids = list(motor_ids)
        self._name = {sid: f"j{sid}" for sid in self.motor_ids}
        self._bus_factory = bus_factory
        self._bus = None

    def _default_factory(self, port, motors):
        from lerobot.motors.feetech import FeetechMotorsBus  # lazy
        return FeetechMotorsBus(port=port, motors=motors)

    def open(self):
        from lerobot.motors import Motor, MotorNormMode  # lazy
        motors = {
            self._name[sid]: Motor(id=sid, model=self._MODEL,
                                   norm_mode=MotorNormMode.RANGE_M100_100)
            for sid in self.motor_ids
        }
        factory = self._bus_factory or self._default_factory
        try:
            self._bus = factory(self.port, motors)
            self._bus.connect(handshake=False)   # open port; motor presence surfaces on read
            self._bus.set_baudrate(self.baud)
        except ArmError:
            raise
        except Exception as e:                    # port/SDK failure -> our error code
            raise ArmError("E_NO_MOTORS", f"could not open motor bus {self.port}: {e}") from e

    # A single dropped status packet is common on the Feetech serial bus while a
    # motor is drawing current; retry a couple of times before giving up so a
    # transient miss doesn't abort a move or a calibration capture. Applies to
    # BOTH reads and writes (goal/torque), which the same noise can drop.
    _RETRY = 2

    def _io(self, sid: int, what: str, fn):
        """Run one bus call, surfacing any driver/SDK failure (dropped packet,
        latched servo fault like Overheat/OverEle, comms loss) as a clean
        ArmError instead of a raw RuntimeError, so callers can catch/handle it."""
        try:
            return fn()
        except ArmError:
            raise
        except Exception as e:
            raise ArmError("E_NO_MOTORS", f"motor id {sid} {what} failed: {e}") from e

    def read_steps(self, sid: int) -> int:
        name = self._name[sid]
        return int(self._io(sid, "read", lambda: self._bus.read(
            "Present_Position", name, normalize=False, num_retry=self._RETRY)))

    def setup(self, sid: int, acc: int, speed: int):
        name = self._name[sid]
        self._io(sid, "setup", lambda: (
            self._bus.write("Acceleration", name, int(acc), normalize=False, num_retry=self._RETRY),
            self._bus.write("Goal_Velocity", name, int(speed), normalize=False, num_retry=self._RETRY),
            self._bus.enable_torque(name, num_retry=self._RETRY)))

    def write_goal(self, sid: int, steps: int):
        name = self._name[sid]
        self._io(sid, "write_goal", lambda: self._bus.write(
            "Goal_Position", name, int(steps), normalize=False, num_retry=self._RETRY))

    def engage(self, sid: int):
        """Torque ON without touching accel/speed (hold at the current goal)."""
        name = self._name[sid]
        self._io(sid, "engage", lambda: self._bus.enable_torque(name, num_retry=self._RETRY))

    def release(self, sid: int):
        name = self._name[sid]
        self._io(sid, "release", lambda: self._bus.disable_torque(name, num_retry=self._RETRY))

    def close(self):
        if self._bus is not None:
            # Do NOT disable torque on close: moves leave the arm holding its
            # pose, and dropping torque here would let it fall.
            self._bus.disconnect(disable_torque=False)
            self._bus = None

    # --- LeRobot calibration facility (Story 1.6: servo range/wrap) ----------
    # These delegate to LeRobot's homing + range-of-motion + calibration write.
    # They are READ/CONFIG only (torque is off, the human moves the arm) — no
    # autonomous motion, so they live below the Arm safety layer like reads do.

    def _names(self, ids):
        ids = self.motor_ids if ids is None else ([ids] if isinstance(ids, int) else list(ids))
        return [self._name[s] for s in ids], list(ids)

    def set_homing(self, ids=None) -> dict:
        """Re-centre each joint on its CURRENT position (half-turn homing).
        Returns ``{motor_id: homing_offset}``. Torque must already be off."""
        names, ids = self._names(ids)
        offsets = self._bus.set_half_turn_homings(names)
        return {sid: int(offsets[self._name[sid]]) for sid in ids}

    def record_ranges(self, ids=None):
        """Interactively record min/max steps while the joints are moved by hand
        (LeRobot streams positions and waits for ENTER). Returns
        ``(mins_by_id, maxes_by_id)`` in raw steps."""
        names, ids = self._names(ids)
        mins, maxes = self._bus.record_ranges_of_motion(names)
        return ({sid: int(mins[self._name[sid]]) for sid in ids},
                {sid: int(maxes[self._name[sid]]) for sid in ids})

    def write_calibration(self, cal_by_id: dict) -> None:
        """Persist calibration to the motors (homing offset + position limits).
        ``cal_by_id`` maps motor id -> {homing_offset, range_min, range_max,
        drive_mode?}."""
        from lerobot.motors import MotorCalibration  # lazy
        cal = {
            self._name[sid]: MotorCalibration(
                id=sid, drive_mode=int(c.get("drive_mode", 0)),
                homing_offset=int(c["homing_offset"]),
                range_min=int(c["range_min"]), range_max=int(c["range_max"]),
            )
            for sid, c in cal_by_id.items()
        }
        self._bus.write_calibration(cal)

    def recenter(self, sid: int, mid_steps) -> int:
        """Shift the homing offset so the current-frame reading ``mid_steps``
        becomes centre (2048). CONFIG WRITE ONLY — torque is untouched, the joint
        does NOT move. Returns the new homing offset, reduced into the register's
        +/-2047 range (the encoder wraps mod a full turn, so it's equivalent)."""
        name = self._name[sid]

        def op():
            rev = STEPS_PER_REV
            h_old = int(self._bus.read("Homing_Offset", name, normalize=False, num_retry=self._RETRY))
            shift = _CENTER - (round(mid_steps) % rev)
            h_new = ((h_old - shift + rev // 2) % rev) - rev // 2
            self._bus.write("Homing_Offset", name, h_new, num_retry=self._RETRY)
            return h_new

        return self._io(sid, "recenter", op)


# --- The safe-motion interface ----------------------------------------------

class Arm:
    """Owns the driver handle and enforces limits/caps/stop on every command."""

    def __init__(self, cfg: dict | None = None, *, bus=None,
                 port=None, baud=None, motor_ids=None):
        if cfg is None:
            cfg = _config.load_config()
        arm_cfg = dict((cfg or {}).get("arm") or {})
        safety_cfg = dict((cfg or {}).get("safety") or {})
        self.port = port or arm_cfg.get("port", _DEFAULT_PORT)
        self.baud = baud or arm_cfg.get("baud", _DEFAULT_BAUD)
        self.motor_ids = list(motor_ids or arm_cfg.get("motor_ids", _DEFAULT_IDS))
        self.limits = safety_cfg.get("joint_limits_deg") or [None] * len(self.motor_ids)
        self.vel_cap = float(safety_cfg.get("velocity_cap_deg_per_step", _DEFAULT_VEL_CAP))
        self.workspace_box = safety_cfg.get("workspace_box")
        self._stop_path = safety.stop_sentinel_path(cfg)
        self._bus = bus
        self._owns_bus = bus is None

    # connection -------------------------------------------------------------
    def connect(self) -> "Arm":
        if self._bus is None:
            self._bus = _FeetechBus(self.port, self.baud, self.motor_ids)
            self._bus.open()
        return self

    def disconnect(self):
        if self._owns_bus and self._bus is not None:
            self._bus.close()
            self._bus = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.disconnect()

    # reads ------------------------------------------------------------------
    def _read_degs(self):
        return [round(steps_to_deg(self._bus.read_steps(sid)), 2) for sid in self.motor_ids]

    def read_joints(self) -> dict:
        """READ-ONLY snapshot of all joints (no torque, no motion)."""
        raw = [self._bus.read_steps(sid) for sid in self.motor_ids]
        return {
            "joint_pos": [round(steps_to_deg(s), 2) for s in raw],
            "raw_steps": raw,
            "motor_ids": list(self.motor_ids),
            "joint_units": JOINT_UNITS,
        }

    # motion -----------------------------------------------------------------
    def move_to(self, targets_deg, *, tick_s: float = _DEFAULT_TICK_S,
                acc: int = 20, speed: int = 500, stop_path: str | None = None) -> dict:
        """Move every joint to ``targets_deg`` (degrees), enforcing limits, the
        per-tick velocity cap, and the stop sentinel. Returns a result dict."""
        targets = list(targets_deg)
        if len(targets) != len(self.motor_ids):
            raise ArmError("E_OUT_OF_BOUNDS",
                           f"expected {len(self.motor_ids)} targets, got {len(targets)}")

        sp = stop_path or self._stop_path
        warnings: list[str] = []
        if self.workspace_box:
            cli.log("WARN: workspace_box set but Cartesian bounds are not enforced in v1 "
                    "(joint-limits only; FK lands later)")

        # 1) clamp to soft joint limits
        clamped, flags = safety.clamp_to_limits(targets, self.limits)
        if any(flags):
            bad = [self.motor_ids[i] for i, f in enumerate(flags) if f]
            cli.log(f"WARN E_OUT_OF_BOUNDS: target(s) for motor {bad} clamped to soft limits")
            warnings.append("E_OUT_OF_BOUNDS")

        # 2) refuse to even start if already stopped
        if safety.stop_requested(path=sp):
            return self._result(False, self._read_degs(), stopped=True, warnings=warnings,
                                error=("E_STOPPED", "stop sentinel present; motion refused"))

        # 3) subdivide so no single tick exceeds the velocity cap
        cur = self._read_degs()
        deltas = [t - c for t, c in zip(clamped, cur)]
        max_delta = max((abs(d) for d in deltas), default=0.0)
        n = max(1, math.ceil(max_delta / self.vel_cap)) if max_delta > 1e-9 else 0

        # Before enabling torque, pin each joint's goal to its PRESENT position
        # (only when actually moving), so a just-relaxed joint holds where it is
        # instead of snapping to a stale Goal_Position register (the observed
        # servo "jerk"). Mirrors hold().
        for sid, c in zip(self.motor_ids, cur):
            if n:
                self._bus.write_goal(sid, deg_to_steps(c))
            self._bus.setup(sid, acc, speed)

        executed = 0
        for i in range(1, n + 1):
            if safety.stop_requested(path=sp):  # checked EVERY tick
                return self._result(False, self._read_degs(), stopped=True, warnings=warnings,
                                    error=("E_STOPPED", f"halted after {executed}/{n} ticks"))
            frac = i / n
            for sid, c, d in zip(self.motor_ids, cur, deltas):
                self._bus.write_goal(sid, deg_to_steps(c + d * frac))
            executed += 1
            if tick_s:
                time.sleep(tick_s)

        return self._result(True, self._read_degs(), warnings=warnings, increments=executed)

    def step(self, deltas_deg, **kw) -> dict:
        """Relative move: current + deltas_deg, through the same safety path."""
        cur = self._read_degs()
        if len(deltas_deg) != len(cur):
            raise ArmError("E_OUT_OF_BOUNDS",
                           f"expected {len(cur)} deltas, got {len(deltas_deg)}")
        return self.move_to([c + d for c, d in zip(cur, deltas_deg)], **kw)

    def _resolve_ids(self, ids):
        if ids is None:
            return list(self.motor_ids)
        ids = [ids] if isinstance(ids, int) else list(ids)
        bad = [i for i in ids if i not in self.motor_ids]
        if bad:
            raise ArmError("E_OUT_OF_BOUNDS", f"unknown motor id(s) {bad}; have {self.motor_ids}")
        return ids

    def relax(self, ids=None):
        """Release torque on the given joints (default: all), de-energizing them.

        Moves normally leave the arm holding position; call this to power joints
        down — e.g. to support a joint by hand during range calibration."""
        for sid in self._resolve_ids(ids):
            self._bus.release(sid)

    def hold(self, ids=None):
        """Energize the given joints (default: all) to HOLD their current pose.

        Reads each joint's present position and writes it back as the goal
        BEFORE enabling torque, so the joint clamps where it already is instead
        of snapping to a stale goal register. The counterpart to :meth:`relax`;
        used to keep the rest of the arm supported while one joint is freed."""
        for sid in self._resolve_ids(ids):
            cur = self._bus.read_steps(sid)
            self._bus.write_goal(sid, cur)
            self._bus.engage(sid)

    # --- joint-range calibration (Story 1.6, FR-11) -------------------------

    def home(self, ids=None) -> list:
        """Re-zero: power the joints DOWN, then set their CURRENT pose as centre.

        Position the arm at its neutral mid-pose FIRST, then call this. Each
        joint's encoder is re-homed (via LeRobot) so its present position reads
        ~0deg and the encoder wrap (4095<->0) sits ~180deg away — so later
        position-mode moves within the soft limits never cross it. Torque is
        released first because changing the homing offset under load can jump
        the joint. Returns per-joint ``{motor_id, homing_offset, deg_after}``."""
        ids = self._resolve_ids(ids)
        self.relax(ids)                                   # MUST be torque-off
        offsets = self._bus.set_homing(ids)
        return [
            {"motor_id": s, "homing_offset": offsets[s],
             "deg_after": round(steps_to_deg(self._bus.read_steps(s)), 2)}
            for s in ids
        ]

    def record_ranges(self, ids=None) -> list:
        """Hand-sweep range capture: torque OFF, then move each joint through its
        full safe range while LeRobot records min/max (press ENTER to finish).

        Returns per-joint ``{motor_id, min_steps, max_steps, min_deg, max_deg}``
        in the re-homed frame. Run :meth:`home` first so the range can't straddle
        the encoder wrap."""
        ids = self._resolve_ids(ids)
        self.relax(ids)
        mins, maxes = self._bus.record_ranges(ids)
        return [
            {"motor_id": s, "min_steps": mins[s], "max_steps": maxes[s],
             "min_deg": round(steps_to_deg(mins[s]), 2),
             "max_deg": round(steps_to_deg(maxes[s]), 2)}
            for s in ids
        ]

    def write_calibration(self, cal_by_id: dict) -> None:
        """Persist homing offsets + position limits to the motors (defense in
        depth: the servos themselves then refuse out-of-range goals)."""
        self._bus.write_calibration(cal_by_id)

    def recenter(self, sid, mid_steps) -> int:
        """Motion-free re-zero of one joint: make ``mid_steps`` (a present reading
        in the CURRENT frame — e.g. the midpoint of a hand-sweep) the new 0deg by
        shifting the homing offset. NO motion, so it's safe even for a gravity-
        loaded joint (this is what avoids the powered-recenter overload). Torque
        should be off. Verifies the shift took, then returns the new offset."""
        self._resolve_ids([sid])
        rev = STEPS_PER_REV
        pres_old = self._bus.read_steps(sid)
        shift = _CENTER - (round(mid_steps) % rev)
        offset = self._bus.recenter(sid, mid_steps)
        pres_new = self._bus.read_steps(sid)
        expected = (pres_old + shift) % rev
        err = min((pres_new - expected) % rev, (expected - pres_new) % rev)
        if err > 6:
            raise ArmError("E_CALIB_REQUIRED",
                           f"motor {sid} re-center off by {err} steps (homing write didn't take)")
        return offset

    def _result(self, ok, joint_pos, *, stopped=False, warnings=None, error=None, increments=0):
        return {
            "ok": ok,
            "joint_pos": joint_pos,
            "joint_units": JOINT_UNITS,
            "motor_ids": list(self.motor_ids),
            "stopped": stopped,
            "clamped": bool(warnings and "E_OUT_OF_BOUNDS" in warnings),
            "warnings": list(warnings or []),
            "increments": increments,
            "error": {"code": error[0], "message": error[1]} if error else None,
        }


# --- Module-level convenience (short-lived connection per call) --------------

def read_joints(port=None, baud=None, motor_ids=None, *, cfg=None, bus=None) -> dict:
    with Arm(cfg=cfg, bus=bus, port=port, baud=baud, motor_ids=motor_ids) as a:
        return a.read_joints()


def move_to(targets_deg, *, cfg=None, bus=None, **kw) -> dict:
    with Arm(cfg=cfg, bus=bus) as a:
        return a.move_to(targets_deg, **kw)


def step(deltas_deg, *, cfg=None, bus=None, **kw) -> dict:
    with Arm(cfg=cfg, bus=bus) as a:
        return a.step(deltas_deg, **kw)


def relax(ids=None, *, cfg=None, bus=None) -> None:
    with Arm(cfg=cfg, bus=bus) as a:
        a.relax(ids)


def hold(ids=None, *, cfg=None, bus=None) -> None:
    with Arm(cfg=cfg, bus=bus) as a:
        a.hold(ids)
