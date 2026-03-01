"""Apply a task patch to the repository.

Usage::

    python scripts/apply_task.py task_01_token_expiry_bypass

The script:
1. Validates that the working tree is clean (no uncommitted changes).
2. Locates the requested ``.patch`` file under the ``tasks/`` directory.
3. Applies the patch with ``git apply``.
4. Prints the name of the test(s) that are expected to fail.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Registry: map task name → expected failing test node-ids (for guidance)
# ---------------------------------------------------------------------------

TASK_REGISTRY: dict[str, list[str]] = {
    "task_01_token_expiry_bypass": [
        "tests/test_auth.py::TestTokens::test_decode_expired_token",
    ],
    "task_02_project_tags_inverted": [
        "tests/test_projects.py::TestProjectTags::test_create_with_tags",
        "tests/test_projects.py::TestProjectTags::test_update_tags",
    ],
    "task_03_empty_name_accepted": [
        "tests/test_projects.py::TestCreateProject::test_create_empty_name_raises",
        "tests/test_tasks.py::TestCreateTask::test_create_empty_title_raises",
    ],
    "task_04_audit_count_broken": [
        "tests/test_audit.py::TestAuditService::test_count_total",
    ],
    "task_05_email_exists_always_false": [
        "tests/test_users.py::TestCreateUser::test_create_duplicate_email_raises",
        "tests/test_auth.py::TestRegister::test_register_duplicate_email_raises",
    ],
}

REPO_ROOT = Path(__file__).parent.parent


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=check)


def _ensure_clean_tree() -> None:
    """Abort if there are uncommitted changes in the working tree."""
    result = _run(["git", "status", "--porcelain"])
    lines = [ln for ln in result.stdout.splitlines() if not ln.startswith("??")]
    if lines:
        print("ERROR: Working tree is not clean.  Commit or stash your changes first.")
        for ln in lines:
            print(f"  {ln}")
        sys.exit(1)


def _find_patch(task_name: str) -> Path:
    """Return the path to the patch file for *task_name*."""
    # Accept bare name (task_01_…) or full filename (task_01_….patch)
    name = task_name.removesuffix(".patch")
    patch_path = REPO_ROOT / "tasks" / f"{name}.patch"
    if not patch_path.exists():
        available = sorted(p.stem for p in (REPO_ROOT / "tasks").glob("*.patch"))
        print(f"ERROR: Patch not found: {patch_path}")
        print("Available tasks:")
        for t in available:
            print(f"  {t}")
        sys.exit(1)
    return patch_path


def _apply_patch(patch_path: Path) -> None:
    """Apply *patch_path* with ``git apply``."""
    result = _run(["git", "apply", str(patch_path)], check=False)
    if result.returncode != 0:
        print("ERROR: git apply failed:")
        print(result.stderr)
        sys.exit(1)
    print(f"Patch applied: {patch_path.name}")


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(f"Usage: python {sys.argv[0]} <task_name>")
        sys.exit(1)

    task_name = args[0].removesuffix(".patch")

    _ensure_clean_tree()
    patch_path = _find_patch(task_name)
    _apply_patch(patch_path)

    expected = TASK_REGISTRY.get(task_name, [])
    if expected:
        print("\nExpected failing test(s):")
        for t in expected:
            print(f"  {t}")
        print(f"\nRun:  pytest {' '.join(expected)}")
    else:
        print("\n(No failing tests registered for this task.)")

    print("\nTo reset the repository: python scripts/reset_repo.py")


if __name__ == "__main__":
    main()
