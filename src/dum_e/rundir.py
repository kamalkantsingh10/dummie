"""Run-directory layout helpers.

Owns ``runs/<UTC-compact-ts>/`` with ``clips/`` and ``frames/`` subdirs and the
frame/clip filename conventions (frozen in architecture Implementation Patterns
§D). Implemented in Story 1.3.

Filename conventions:
    frames/<episode_id>_<step:04d>.png
    clips/<episode_id>.mp4
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

FRAME_NAME = "frames/{episode_id}_{step:04d}.png"
CLIP_NAME = "clips/{episode_id}.mp4"


def compact_ts(dt: datetime | None = None) -> str:
    """UTC timestamp as a filesystem-safe compact string, e.g. 20260620T204231Z."""
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def new_run_dir(root: str = "runs", *, ts: str | None = None) -> str:
    """Create ``<root>/<UTC-compact-ts>/`` with ``frames/`` and ``clips/`` and
    return its path."""
    run = Path(root) / (ts or compact_ts())
    (run / "frames").mkdir(parents=True, exist_ok=True)
    (run / "clips").mkdir(parents=True, exist_ok=True)
    return str(run)


def frame_path(run_dir: str, episode_id: str, step: int = 0) -> str:
    """Path for a saved still under ``run_dir`` following the frame convention."""
    return str(Path(run_dir) / FRAME_NAME.format(episode_id=episode_id, step=int(step)))


def clip_path(run_dir: str, episode_id: str) -> str:
    """Path for a saved clip under ``run_dir`` following the clip convention."""
    return str(Path(run_dir) / CLIP_NAME.format(episode_id=episode_id))
