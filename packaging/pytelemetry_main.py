"""Frozen-app entry point for PyInstaller. Owner: release-engineer."""

from __future__ import annotations

import sys

from pytelemetry.cli import main

if __name__ == "__main__":
    sys.exit(main())
