"""Dum-E — autonomous robotic videographer control library.

This package is the importable, testable control layer. It is driven by:
  - thin CLI adapters in ``scripts/`` (which print the JSON envelope from
    :mod:`dum_e.cli`), and
  - the Claude Code Skill director in ``.claude/skills/dum-e/SKILL.md``.

Keep this ``__init__`` lightweight: do NOT import heavy/optional dependencies
(opencv, lerobot, torch) at package import time. Modules that need them import
them lazily inside functions so ``import dum_e`` always succeeds.
"""

__version__ = "0.0.1"

__all__ = ["__version__"]
