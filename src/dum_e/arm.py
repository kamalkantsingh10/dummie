"""Arm control — the SOLE path to the servos (safety chokepoint, FR-14).

NOTHING else in the codebase may import the motor driver (LeRobot/Feetech).
Every motion routes through here and is clamped to soft joint/workspace limits,
capped by velocity, and aborted by the stop sentinel. Read path lands in Story
1.4; full actuation + limits + stop land in Story 1.5.

Joint values are degrees (``joint_units = "deg"``) to match the shot-log schema.
"""

from __future__ import annotations

JOINT_UNITS = "deg"
N_JOINTS = 6


def read_joints(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("arm.read_joints lands in Story 1.4")


def move_to(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("arm.move_to lands in Story 1.5")
