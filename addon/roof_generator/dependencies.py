# SPDX-License-Identifier: GPL-3.0-or-later
"""Find a host interpreter that can actually run pip."""

from pathlib import Path
import shutil
import subprocess


def find_host_python(selected="", *, blender_binary=""):
    candidates = [selected] if selected else [
        shutil.which(name) for name in ("python3", "python", "py")
    ]
    failures = []
    seen = set()
    for host in candidates:
        if not host:
            continue
        path = Path(host).resolve()
        if path in seen:
            continue
        seen.add(path)
        if blender_binary and path == Path(blender_binary).resolve():
            failures.append(f"{host}: Blender is not a host Python executable")
            continue
        try:
            run = subprocess.run(
                [host, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if run.returncode == 0 and run.stdout.strip():
                return host
            detail = (run.stderr or run.stdout).strip() or "pip produced no output"
            failures.append(f"{host}: {detail}")
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"{host}: {exc}")
    detail = "; ".join(failures) or "no Python executable found on PATH"
    raise RuntimeError(
        "Set a working host Python executable with pip in addon preferences. "
        + detail
    )
