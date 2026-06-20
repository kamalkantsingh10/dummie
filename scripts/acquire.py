#!/usr/bin/env python3
"""acquire — phrase -> bounding box via selected backend. Story 2.1 / 2.6."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/acquire.py is implemented in Story 2.1")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
