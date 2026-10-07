# SPDX-License-Identifier: GPL-3.0-or-later
"""Install matching binary wheels locally, using a host Python with pip.

python install_roof_dependencies.py --blender /path/to/blender
Works with a local Windows or Linux Blender. No system Python install is changed.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument(
        "--addon-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "addon" / "roof_generator",
        help="Installed or source addon directory",
    )
    args = parser.parse_args()
    expression = (
        'import sys,json; print("ROOF_PYTHON="+json.dumps(list(sys.version_info[:2])))'
    )
    process = subprocess.run(
        [
            args.blender,
            "--background",
            "--factory-startup",
            "--python-expr",
            expression,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    line = next(
        (
            line
            for line in process.stdout.splitlines()
            if line.startswith("ROOF_PYTHON=")
        ),
        None,
    )
    if line is None:
        raise RuntimeError("Blender did not report its Python version")
    major, minor = json.loads(line.split("=", 1)[1])
    target = args.addon_dir.resolve() / ".roof-deps" / f"cp{major}{minor}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--only-binary=:all:",
            "--no-deps",
            "--python-version",
            f"{major}.{minor}",
            "--target",
            str(target),
            "-r",
            str(Path(__file__).resolve().parent / "requirements-roof.txt"),
        ],
        check=True,
    )
    print(
        f"Installed final-roof dependency for Blender Python {major}.{minor}: {target}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
