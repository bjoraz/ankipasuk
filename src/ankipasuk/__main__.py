"""Entry point for ``python -m ankipasuk``."""

import sys

from .webgui import main

if __name__ == "__main__":
    sys.exit(main())
