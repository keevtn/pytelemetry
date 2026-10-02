"""Build the PyTelemetry executable with PyInstaller. Owner: release-engineer.

    uv run python packaging/build.py            # onedir (default) -> dist/PyTelemetry/
    uv run python packaging/build.py --onefile  # single file     -> dist/PyTelemetry[.exe]

Then zips the result as dist/PyTelemetry-<os>-<arch>.zip for CI upload.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "pytelemetry.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _os_arch() -> str:
    system = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
        platform.system(), platform.system().lower()
    )
    arch = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(arch, arch)
    return f"{system}-{arch}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true", help="single-file build")
    args = parser.parse_args()

    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)

    env = dict(os.environ)
    env["PYI_ONEFILE"] = "1" if args.onefile else "0"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD),
            str(SPEC),
        ],
        check=True,
        cwd=str(ROOT / "packaging"),
        env=env,
    )

    target = DIST / ("PyTelemetry.exe" if args.onefile and platform.system() == "Windows" else "PyTelemetry")
    zip_base = DIST / f"PyTelemetry-{_os_arch()}"
    if args.onefile:
        # zip just the single binary
        staging = DIST / "PyTelemetry"
        staging.mkdir(exist_ok=True)
        shutil.copy2(target, staging / target.name)
        shutil.make_archive(str(zip_base), "zip", root_dir=str(staging))
    else:
        shutil.make_archive(str(zip_base), "zip", root_dir=str(DIST / "PyTelemetry"))
    print(f"built {zip_base}.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
