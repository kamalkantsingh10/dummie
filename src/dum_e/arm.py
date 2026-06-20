"""Arm control — the SOLE path to the servos (safety chokepoint, FR-14).

NOTHING else in the runtime/library may import the motor driver. Every motion
routes through here and is, on every control tick:
  * clamped to the configured soft joint limits (E_OUT_OF_BOUNDS, logged),
  * capped by the per-step velocity limit (a move is subdivided into <=cap ticks),
  * aborted the instant the stop sentinel appears (E_STOPPED), holding position.

Driver = Feetech STS3215 bus via ``scservo_sdk``, lazy-imported and fully
encapsulated in :class:`_FeetechBus` so ``import dum_e.arm`` works with no SDK or
hardware, and so a driver/version change touches only this file.

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
    A_TORQUE, A_ACC, A_GOAL, A_SPEED, A_POS = 40, 41, 42, 46, 56
    _PROTOCOL_END = 0

    def __init__(self, port: str, baud: int):
        self.port, self.baud = port, baud
        self._port = None
        self._ph = None

    def open(self):
        from scservo_sdk import PortHandler, PacketHandler  # lazy
        self._port = PortHandler(self.port)
        if not self._port.openPort():
            raise ArmError("E_NO_MOTORS", f"could not open motor bus {self.port}")
        if not self._port.setBaudRate(self.baud):
            raise ArmError("E_NO_MOTORS", f"could not set baud {self.baud} on {self.port}")
        self._ph = PacketHandler(self._PROTOCOL_END)

    def read_steps(self, sid: int) -> int:
        from scservo_sdk import COMM_SUCCESS
        pos, comm, _ = self._ph.read2ByteTxRx(self._port, sid, self.A_POS)
        if comm != COMM_SUCCESS:
            raise ArmError("E_NO_MOTORS", f"motor id {sid} did not respond (comm={comm})")
        return int(pos)

    def setup(self, sid: int, acc: int, speed: int):
        self._ph.write1ByteTxRx(self._port, sid, self.A_ACC, acc)
        self._ph.write2ByteTxRx(self._port, sid, self.A_SPEED, speed)
        self._ph.write1ByteTxRx(self._port, sid, self.A_TORQUE, 1)

    def write_goal(self, sid: int, steps: int):
        self._ph.write2ByteTxRx(self._port, sid, self.A_GOAL, steps)

    def release(self, sid: int):
        self._ph.write1ByteTxRx(self._port, sid, self.A_TORQUE, 0)

    def close(self):
        if self._port is not None:
            self._port.closePort()
            self._port = None


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
            self._bus = _FeetechBus(self.port, self.baud)
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

        for sid in self.motor_ids:
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

    def relax(self):
        """Release torque on all joints (de-energized). Moves should normally
        leave the arm holding position; call this to power the joints down."""
        for sid in self.motor_ids:
            self._bus.release(sid)

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


def relax(*, cfg=None, bus=None) -> None:
    with Arm(cfg=cfg, bus=bus) as a:
        a.relax()
