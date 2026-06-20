#!/usr/bin/env python3
"""survey — capture a frame (Story 1.3) and list scene subjects (Story 2.2)."""
import sys

from dum_e import cli


def main(argv=None) -> int:
    return cli.fail(cli.E_NOT_IMPLEMENTED, "scripts/survey.py capture mode is implemented in Story 1.3")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
