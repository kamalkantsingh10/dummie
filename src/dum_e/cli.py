"""Canonical CLI JSON-stdout envelope (frozen script I/O contract).

Every script in ``scripts/`` returns its result through this helper so the
contract never drifts:

    stdout  ->  exactly ONE JSON object: {"ok", "data", "error", "artifacts"}
    stderr  ->  all human/diagnostic logging
    exit    ->  0 iff ok is True

Field names are snake_case; paths are POSIX, relative to the run dir.
See architecture.md "Implementation Patterns A. Script I/O Contract".
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Sequence


# ---- Namespaced error codes (architecture Implementation Patterns E) --------
E_NO_CAMERA = "E_NO_CAMERA"
E_TARGET_NOT_FOUND = "E_TARGET_NOT_FOUND"
E_LOST_LOCK = "E_LOST_LOCK"
E_OUT_OF_BOUNDS = "E_OUT_OF_BOUNDS"
E_STOPPED = "E_STOPPED"
E_CALIB_REQUIRED = "E_CALIB_REQUIRED"
E_NO_MOTORS = "E_NO_MOTORS"
E_NOT_IMPLEMENTED = "E_NOT_IMPLEMENTED"


def envelope(
    ok: bool,
    data: Mapping[str, Any] | None = None,
    error: Mapping[str, str] | None = None,
    artifacts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical result object (pure; does no I/O)."""
    return {
        "ok": bool(ok),
        "data": dict(data) if data else {},
        "error": dict(error) if error else None,
        "artifacts": list(artifacts) if artifacts else [],
    }


def log(*args: Any) -> None:
    """Write a human/diagnostic line to stderr (never stdout)."""
    print(*args, file=sys.stderr)


def emit(result: Mapping[str, Any], *, stream=None) -> int:
    """Write one JSON object to stdout and return the process exit code."""
    stream = stream if stream is not None else sys.stdout
    stream.write(json.dumps(result))
    stream.flush()
    return 0 if result.get("ok") else 1


def ok(
    data: Mapping[str, Any] | None = None,
    artifacts: Sequence[str] | None = None,
    *,
    stream=None,
) -> int:
    """Emit a success envelope and return exit code 0."""
    return emit(envelope(True, data=data, artifacts=artifacts), stream=stream)


def fail(code: str, message: str, *, stream=None) -> int:
    """Emit a failure envelope and return exit code 1."""
    return emit(envelope(False, error={"code": code, "message": message}), stream=stream)
