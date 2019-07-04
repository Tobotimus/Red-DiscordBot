#!/usr/bin/env python3
import sys
from pathlib import Path

import polib

PROJECT_ROOT = Path(__file__).parents[1].absolute()
LOCALEDIR = PROJECT_ROOT / "redbot" / "locales"


def main() -> int:
    for pofile_pth in PROJECT_ROOT.glob("redbot/**/locales/*.po"):
        package = ".".join(map(str, pofile_pth.relative_to(PROJECT_ROOT).parents[1].parts))
        language = pofile_pth.stem
        mofile_pth = LOCALEDIR / language / "LC_MESSAGES" / f"{package}.mo"
        mofile_pth.parent.mkdir(parents=True, exist_ok=True)

        polib.pofile(str(pofile_pth)).save_as_mofile(str(mofile_pth))

    return 0


if __name__ == "__main__":
    sys.exit(main())
