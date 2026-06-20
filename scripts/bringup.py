#!/usr/bin/env python3
"""bringup — verify motor comms (read-only) + camera capture. Story 1.4."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/bringup.py is implemented in Story 1.4")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
