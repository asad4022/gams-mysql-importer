"""Application package for the MySQL to GAMS importer."""

from __future__ import annotations

import sys


MIN_PYTHON = (3, 11)

if sys.version_info < MIN_PYTHON:
    version_text = ".".join(str(part) for part in MIN_PYTHON)
    raise RuntimeError(
        f"MySQL to GAMS Importer requires Python {version_text} or newer. "
        "Please recreate the virtual environment with Python 3.11."
    )


__all__: list[str] = []
