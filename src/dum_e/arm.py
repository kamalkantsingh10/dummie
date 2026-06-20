"""Arm control — the SOLE path to the servos (safety chokepoint, FR-14).

NOTHING else in the codebase may import the motor driver (Feetech/LeRobot).
Every motion routes through here and is clamped to soft joint/workspace limits,
capped by velocity, and aborted by the stop sentinel. The READ path lands in
Story 1.4; full actuation + limits + stop land in Story 1.5.

Joint values are degrees (``joint_units = "deg"``) to match the shot-log schema.
The driver is the Feetech STS3215 bus via ``scservo_sdk`` (lazy-imported so
``import dum_e.arm`` works without the SDK or hardware present).
"""

from __future__ import annotations

JOINT_UNITS = "deg"
N_JOINTS = 6
STEPS_PER_REV = 4096                # STS3215: 4096 steps = 360°
_DEG_PER_STEP = 360.0 / STEPS_PER_REV
_ADDR_PRESENT_POSITION = 56        # STS/SMS control table
_PROTOCOL_END = 0                  # Feetech STS/SMS use protocol_end=0

_DEFAULT_PORT = "/dev/ttyUSB0"
_DEFAULT_BAUD = 1000000
_DEFAULT_IDS = [1, 2, 3, 4, 5, 6]


class ArmError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _steps_to_deg(steps: int) -> float:
    """Raw encoder steps -> degrees (0..360, uncalibrated; Story 1.6 homes zero)."""
    return steps * _DEG_PER_STEP


def _resolve_bus(port, baud, motor_ids, cfg):
    if cfg is None and (port is None or baud is None or motor_ids is None):
        from dum_e import config as _config
        cfg = _config.load_config()
    arm_cfg = dict((cfg or {}).get("arm") or {})
    return (
        port or arm_cfg.get("port", _DEFAULT_PORT),
        baud or arm_cfg.get("baud", _DEFAULT_BAUD),
        list(motor_ids or arm_cfg.get("motor_ids", _DEFAULT_IDS)),
    )


def read_joints(port=None, baud=None, motor_ids=None, *, cfg=None) -> dict:
    """Read present positions of all joints. READ-ONLY — commands no motion.

    Returns ``{joint_pos:[deg], raw_steps:[int], motor_ids:[int], joint_units}``.
    Raises :class:`ArmError` (``E_NO_MOTORS``) if the bus can't open or any
    configured motor fails to respond — the green-light gate must be unambiguous.
    """
    from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS  # lazy

    port, baud, motor_ids = _resolve_bus(port, baud, motor_ids, cfg)
    handler = PortHandler(port)
    if not handler.openPort():
        raise ArmError("E_NO_MOTORS", f"could not open motor bus {port} (powered / connected?)")
    try:
        if not handler.setBaudRate(baud):
            raise ArmError("E_NO_MOTORS", f"could not set baud {baud} on {port}")
        packet = PacketHandler(_PROTOCOL_END)
        raw: list[int] = []
        for sid in motor_ids:
            pos, comm, err = packet.read2ByteTxRx(handler, sid, _ADDR_PRESENT_POSITION)
            if comm != COMM_SUCCESS:
                raise ArmError("E_NO_MOTORS", f"motor id {sid} did not respond (comm={comm})")
            raw.append(int(pos))
        return {
            "joint_pos": [round(_steps_to_deg(s), 2) for s in raw],
            "raw_steps": raw,
            "motor_ids": list(motor_ids),
            "joint_units": JOINT_UNITS,
        }
    finally:
        handler.closePort()


def move_to(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("arm.move_to lands in Story 1.5")
