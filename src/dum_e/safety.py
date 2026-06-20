"""Stop-sentinel + bounds helpers used by arm.py (FR-14).

The stop sentinel is a well-known file; ``arm.py`` checks it on every control
tick and halts immediately when present (returns ``E_STOPPED``). Drop the file
(``safety.request_stop()`` or ``touch runs/STOP``) to halt all motion.

This module does pure file/bounds logic — it never touches the motor driver.
"""

from __future__ import annotations

import os
from pathlib import Path

STOP_SENTINEL_DEFAULT = "runs/STOP"


def stop_sentinel_path(cfg: dict | None = None, *, path: str | None = None) -> str:
    """Resolve the sentinel path: explicit ``path`` > config > default."""
    if path is not None:
        return path
    if cfg is None:
        from dum_e import config as _config
        cfg = _config.load_config()
    return ((cfg or {}).get("safety") or {}).get("stop_sentinel", STOP_SENTINEL_DEFAULT)


def stop_requested(cfg: dict | None = None, *, path: str | None = None) -> bool:
    """True when the stop sentinel is present (checked every control tick)."""
    return Path(stop_sentinel_path(cfg, path=path)).exists()


def request_stop(cfg: dict | None = None, *, path: str | None = None) -> str:
    """Create the stop sentinel (halts motion at the next tick). Returns its path."""
    p = Path(stop_sentinel_path(cfg, path=path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("stop\n")
    return str(p)


def clear_stop(cfg: dict | None = None, *, path: str | None = None) -> None:
    """Remove the stop sentinel if present (idempotent)."""
    try:
        os.remove(stop_sentinel_path(cfg, path=path))
    except FileNotFoundError:
        pass


def clamp_to_limits(values, limits):
    """Clamp each value to its ``[min, max]`` limit pair.

    Returns ``(clamped_values, clamped_flags)`` where ``clamped_flags[i]`` is
    True iff ``values[i]`` was outside its bounds. ``limits`` entries may be
    ``None`` to leave that joint unbounded.
    """
    out, flags = [], []
    for i, v in enumerate(values):
        lim = limits[i] if i < len(limits) else None
        if not lim:
            out.append(v)
            flags.append(False)
            continue
        lo, hi = lim
        c = min(max(v, lo), hi)
        out.append(c)
        flags.append(c != v)
    return out, flags
