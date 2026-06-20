"""Run-directory layout helpers.

Owns ``runs/<UTC-compact-ts>/`` with ``clips/`` and ``frames/`` subdirs and the
frame/clip filename conventions. Implemented in Story 1.3.
"""

from __future__ import annotations

FRAME_NAME = "frames/{episode_id}_{step:04d}.png"
CLIP_NAME = "clips/{episode_id}.mp4"


def new_run_dir(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("rundir.new_run_dir lands in Story 1.3")
