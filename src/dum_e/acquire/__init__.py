"""Pluggable acquire backends (phrase -> bounding box), all CPU.

Backends (architecture D5):
  - claude_box  : Claude-provided approximate box (zero-dependency default) -> Story 2.1
  - yoloe       : primary open-vocab detector (CPU)                          -> Story 2.6
  - yolo_world  : alternative open-vocab detector (CPU)

Selected via ``config.yaml`` key ``acquire_backend`` through the common
:class:`dum_e.acquire.base.AcquireBackend` interface.
"""

__all__ = ["base"]
