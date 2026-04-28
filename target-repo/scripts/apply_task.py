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
from typing import TypedDict

# ---------------------------------------------------------------------------
# Registry: map task name → task type + expected failing test node-ids
# ---------------------------------------------------------------------------


class TaskInfo(TypedDict):
    task_type: str  # "bug_fix" | "feature" | "test_fix"
    failing_tests: list[str]


TASK_REGISTRY: dict[str, TaskInfo] = {
    "task_01_token_expiry_bypass": {
        "task_type": "bug_fix",
        "failing_tests": [
            "tests/test_auth.py::TestTokens::test_decode_expired_token",
        ],
    },
    "task_02_project_tags_inverted": {
        "task_type": "bug_fix",
        "failing_tests": [
            "tests/test_projects.py::TestProjectTags::test_create_with_tags",
            "tests/test_projects.py::TestProjectTags::test_update_tags",
        ],
    },
    "task_03_empty_name_accepted": {
        "task_type": "bug_fix",
        "failing_tests": [
            "tests/test_projects.py::TestCreateProject::test_create_empty_name_raises",
            "tests/test_tasks.py::TestCreateTask::test_create_empty_title_raises",
        ],
    },
    "task_04_audit_count_broken": {
        "task_type": "bug_fix",
        "failing_tests": [
            "tests/test_audit.py::TestAuditService::test_count_total",
        ],
    },
    "task_05_email_exists_always_false": {
        "task_type": "bug_fix",
        "failing_tests": [
            "tests/test_users.py::TestCreateUser::test_create_duplicate_email_raises",
            "tests/test_auth.py::TestRegister::test_register_duplicate_email_raises",
        ],
    },
    "task_06_user_search_stubbed": {
        "task_type": "feature",
        "failing_tests": [
            "tests/test_users.py::TestSearchUsers::test_search_by_username_substring",
            "tests/test_users.py::TestSearchUsers::test_search_by_email_substring",
            "tests/test_users.py::TestSearchUsers::test_search_returns_multiple_matches",
            "tests/test_users.py::TestSearchUsers::test_search_case_insensitive",
        ],
    },
    "task_07_audit_purge_stubbed": {
        "task_type": "feature",
        "failing_tests": [
            "tests/test_audit.py::TestAuditServicePurge::test_purge_old_entries_deletes_stale",
        ],
    },
    "task_08_test_role_assertion_wrong": {
        "task_type": "test_fix",
        "failing_tests": [
            "tests/test_users.py::TestCreateUser::test_create_default_role_is_member",
        ],
    },
    "task_09_test_count_wrong": {
        "task_type": "test_fix",
        "failing_tests": [
            "tests/test_users.py::TestListUsers::test_list_returns_all",
        ],
    },
}

TARGET_REPO_ROOT = Path(__file__).parent.parent


def _git_top_level() -> Path:
    """Return the actual git repository top-level directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=TARGET_REPO_ROOT,
        check=True,
    )
    return Path(result.stdout.strip())


GIT_ROOT = _git_top_level()


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=GIT_ROOT, check=check)


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
    patch_path = TARGET_REPO_ROOT / "tasks" / f"{name}.patch"
    if not patch_path.exists():
        available = sorted(p.stem for p in (TARGET_REPO_ROOT / "tasks").glob("*.patch"))
        print(f"ERROR: Patch not found: {patch_path}")
        print("Available tasks:")
        for t in available:
            print(f"  {t}")
        sys.exit(1)
    return patch_path


def _tracked_changes() -> list[str]:
    """Return tracked working-tree changes from git status porcelain output."""
    result = _run(["git", "status", "--porcelain"])
    return [ln for ln in result.stdout.splitlines() if not ln.startswith("??")]


def _apply_patch(patch_path: Path) -> None:
    """Apply *patch_path* with ``git apply``."""
    result = _run(["git", "apply", str(patch_path)], check=False)
    if result.returncode != 0:
        print("ERROR: git apply failed:")
        print(result.stderr)
        sys.exit(1)

    changed = _tracked_changes()
    if not changed:
        print("ERROR: git apply reported success, but no tracked files changed.")
        print("The patch may have been skipped due to an incorrect path or stale context.")
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

    task_info = TASK_REGISTRY.get(task_name)
    if task_info:
        print(f"\nTask type: {task_info['task_type']}")
        print("\nExpected failing test(s):")
        for t in task_info["failing_tests"]:
            print(f"  {t}")
        print(f"\nRun:  pytest {' '.join(task_info['failing_tests'])}")
    else:
        print("\n(No failing tests registered for this task.)")

    print("\nTo reset the repository: python scripts/reset_repo.py")


if __name__ == "__main__":
    main()
