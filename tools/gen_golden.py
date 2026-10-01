"""Regenerate tests/golden/vectors.json from the unmodified C library. Owner: protocol-engineer.

Usage: python tools/gen_golden.py [--check]
--check regenerates to a temp file and fails (exit 1) on any drift from the committed file. CI runs this.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
VECTORS = GOLDEN / "vectors.json"


def find_compiler() -> str:
    for cc in ("cc", "gcc", "clang"):
        if shutil.which(cc):
            return cc
    sys.exit("no C compiler found (need cc/gcc/clang)")


def generate() -> tuple[str, dict]:
    """Returns (raw harness stdout, parsed JSON). The raw text is written verbatim to keep diffs clean."""
    cc = find_compiler()
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "harness"
        sources = [
            str(ROOT / "firmware" / "Dashboard.c"),
            str(ROOT / "firmware" / "COBS.c"),
            str(GOLDEN / "harness.c"),
        ]
        subprocess.run(
            [cc, "-std=c11", "-O1", "-I", str(ROOT / "firmware"), *sources, "-o", str(exe)],
            check=True,
        )
        out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    return out, json.loads(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail on drift instead of rewriting")
    args = parser.parse_args()

    raw, fresh = generate()
    if args.check:
        committed = json.loads(VECTORS.read_text())
        if fresh != committed:
            print("DRIFT: regenerated vectors differ from tests/golden/vectors.json", file=sys.stderr)
            return 1
        print(f"ok: {len(fresh['vectors'])} vector entries match the firmware")
        return 0
    VECTORS.write_text(raw)
    print(f"wrote {VECTORS} ({len(fresh['vectors'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
