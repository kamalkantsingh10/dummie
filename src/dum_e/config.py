"""Load ``config.yaml`` — the single runtime configuration file.

Scripts call :func:`load_config` to get the parsed mapping, then hand the
relevant slice to a typed config (e.g. :meth:`dum_e.camera.CamConfig.from_config`).
``pyyaml`` is imported lazily so ``import dum_e.config`` stays cheap.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_FILENAME = "config.yaml"


def find_config_path(start: str | None = None) -> str | None:
    """Walk upward from ``start`` (default cwd) looking for ``config.yaml``."""
    here = Path(start) if start else Path.cwd()
    for d in [here, *here.parents]:
        candidate = d / CONFIG_FILENAME
        if candidate.is_file():
            return str(candidate)
    return None


def load_config(path: str | None = None) -> dict:
    """Return the parsed config mapping. Missing file -> empty dict (callers fall
    back to typed defaults). An explicit ``path`` that does not exist raises."""
    import yaml

    if path is None:
        path = find_config_path()
        if path is None:
            return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}
