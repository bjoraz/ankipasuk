"""Makes ``import ankipasuk`` work when these scripts are run directly
(e.g. double-clicked) without the package having been ``pip install``-ed.
If it's already installed (editable or not), this is a no-op."""

import sys
from pathlib import Path

try:
    import ankipasuk  # noqa: F401
except ImportError:
    _src = Path(__file__).resolve().parent.parent / "src"
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
