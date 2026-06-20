"""Stop-sentinel + bounds helpers used by arm.py (FR-14).

Lands in Story 1.5. The stop sentinel is a well-known file; arm.py checks it on
every control tick and halts immediately when present (returns E_STOPPED).
"""

from __future__ import annotations

STOP_SENTINEL_DEFAULT = "runs/STOP"


def stop_requested(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("safety.stop_requested lands in Story 1.5")
