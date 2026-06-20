#!/usr/bin/env python3
"""calibrate — hand-eye self-calibration. Story 1.6."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/calibrate.py is implemented in Story 1.6")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
