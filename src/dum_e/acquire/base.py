"""Acquire backend interface.

A backend turns a target *phrase* + a frame into a precise bounding box
``[x1, y1, x2, y2]`` (absolute integer pixels, origin top-left) paired with
``frame_wh = [w, h]`` — the frozen coordinate convention. Concrete backends
land in Stories 2.1 (claude_box) and 2.6 (yoloe).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AcquireBackend(Protocol):
    """Phrase + frame -> box. Implementations must be CPU-only for v1."""

    name: str

    def locate(self, frame_path: str, phrase: str) -> dict:
        """Return ``{"box": [x1,y1,x2,y2], "frame_wh": [w,h]}`` or raise.

        Raise a lookup error mapped to ``E_TARGET_NOT_FOUND`` when the target
        cannot be located.
        """
        ...
