"""Hand-eye self-calibration: learn the joint->pixel mapping (FR-11).

Measurement, NOT ML training. Lands in Story 1.6. Consumes arm.py (motion) and
camera.py (frames); persists a profile under ``calibration/``.
"""

from __future__ import annotations


def calibrate(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("calibration.calibrate lands in Story 1.6")
