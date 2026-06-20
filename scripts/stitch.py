#!/usr/bin/env python3
"""stitch — concat clips in plan order into the final video. Story 4.4."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/stitch.py is implemented in Story 4.4")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
