# SPDX-License-Identifier: GPL-3.0-or-later
"""Development tools import the same distributable addon source as Blender."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
