#!/usr/bin/env python3
"""photo — capture a single still on request. Story 3.4."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/photo.py is implemented in Story 3.4")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
