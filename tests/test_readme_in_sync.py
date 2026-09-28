"""README.md catalogue blocks must match fallback_models.py.

The tier counts and numbered model lists in README.md used to be hand-edited
and drifted on every catalogue refresh. scripts/sync-readme.py regenerates
them from the generated tuples; this test is the gate that keeps them honest.

Run `python3 scripts/sync-readme.py` after copying a new fallback_models.py.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_readme_in_sync_with_fallback_models():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "sync-readme.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        "README.md catalogue blocks are stale. Fix: python3 scripts/sync-readme.py\n"
        f"{proc.stdout}{proc.stderr}"
    )
