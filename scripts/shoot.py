#!/usr/bin/env python3
"""shoot — track + servo + primitive + record + log one shot. Story 3.x."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/shoot.py is implemented across Stories 2.4/3.2/3.3/3.6")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
