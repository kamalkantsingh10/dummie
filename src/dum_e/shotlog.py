"""Training-grade shot log (FR-13) — the ONLY writer of shots.jsonl.

Validates every entry against ``schemas/shot_log.v1.json`` (frozen v1.0.0,
LeRobotDataset-aligned) or quarantines it. Schema + validator land in Story 3.5;
wiring into the shoot loop lands in Story 3.6.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"


def append_entry(*args, **kwargs):  # pragma: no cover - stub
    raise NotImplementedError("shotlog.append_entry lands in Story 3.5/3.6")
