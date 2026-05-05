"""Reset the repository to its clean baseline state.

Usage::

    python scripts/reset_repo.py

The script discards all uncommitted changes to tracked files by running
``git checkout -- .`` from the repository root.  Untracked files (e.g. a
virtual-environment directory, build artefacts) are left untouched.

Use this after applying a task patch to restore the original source so the
full test suite passes again.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=check)


def _has_changes() -> bool:
    """Return True if tracked files have uncommitted modifications."""
    result = _run(["git", "status", "--porcelain"])
    return any(
        not ln.startswith("??") for ln in result.stdout.splitlines()
    )


def main() -> None:
    if not _has_changes():
        print("Working tree is already clean – nothing to reset.")
        return

    result = _run(["git", "checkout", "--", "."], check=False)
    if result.returncode != 0:
        print("ERROR: git checkout failed:")
        print(result.stderr)
        sys.exit(1)

    print("Repository reset to clean baseline.")
    print("Run pytest to confirm all tests pass:")
    print("  pytest -q")


if __name__ == "__main__":
    main()
