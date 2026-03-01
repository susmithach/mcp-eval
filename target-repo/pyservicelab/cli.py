"""Command-line interface for PyServiceLab.

Usage::

    python -m pyservicelab.cli <command> [options]

Available commands:
    show-config       Print the current application configuration.
    seed-data         Populate the database with sample data.
    create-user       Create a new user account.
    create-project    Create a new project.
    run-tests         Print a message directing to pytest (tests run via pytest).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from pyservicelab.auth.models import Credentials, RegistrationRequest
from pyservicelab.auth.service import AuthService
from pyservicelab.config.loaders import AppConfig
from pyservicelab.core.logging import setup_logging
from pyservicelab.db.audit_repo import AuditRepository
from pyservicelab.db.migrations import run_migrations
from pyservicelab.db.project_repo import ProjectRepository
from pyservicelab.db.sqlite import DatabaseConnection
from pyservicelab.db.task_repo import TaskRepository
from pyservicelab.db.user_repo import UserRepository
from pyservicelab.services.audit_service import AuditService
from pyservicelab.services.project_service import ProjectService
from pyservicelab.services.task_service import TaskService
from pyservicelab.services.user_service import UserService


# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------


def _bootstrap(db_path: Optional[str] = None) -> tuple[AppConfig, DatabaseConnection]:
    """Load config and initialise a database connection."""
    config = AppConfig.load()
    if db_path:
        config.settings.db_path = db_path
    setup_logging(config.settings.log_level)
    db = DatabaseConnection(config.settings.db_path)
    run_migrations(db)
    return config, db


def _build_services(config: AppConfig, db: DatabaseConnection) -> dict:
    """Construct and return all service instances."""
    user_repo = UserRepository(db)
    project_repo = ProjectRepository(db)
    task_repo = TaskRepository(db)
    audit_repo = AuditRepository(db)

    audit_svc = AuditService(
        audit_repo,
        enabled=config.feature_flags.enable_audit_log,
    )
    user_svc = UserService(user_repo, audit_svc)
    auth_svc = AuthService(
        user_repo,
        secret_key=config.settings.secret_key,
        token_expiry_seconds=config.settings.token_expiry_seconds,
    )
    project_svc = ProjectService(project_repo, user_repo, audit_svc)
    task_svc = TaskService(task_repo, project_repo, user_repo, audit_svc)

    return {
        "user": user_svc,
        "auth": auth_svc,
        "project": project_svc,
        "task": task_svc,
        "audit": audit_svc,
    }


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_show_config(args: argparse.Namespace) -> int:
    """Print the current application configuration to stdout."""
    config = AppConfig.load()
    output = config.as_dict()
    print(json.dumps(output, indent=2))
    return 0


def cmd_seed_data(args: argparse.Namespace) -> int:
    """Populate the database with sample users, projects, and tasks."""
    config, db = _bootstrap(getattr(args, "db", None))
    services = _build_services(config, db)
    user_svc: UserService = services["user"]
    project_svc: ProjectService = services["project"]
    task_svc: TaskService = services["task"]

    print("Seeding database…")

    # Create sample users
    try:
        admin = user_svc.create_user(
            username="admin",
            email="admin@example.com",
            password="admin-password-1",
            role="admin",
        )
        print(f"  Created user: {admin.username} (id={admin.id})")
    except Exception as exc:
        print(f"  Skipping admin user (already exists?): {exc}")
        admin = user_svc.get_user_by_username("admin")

    try:
        member = user_svc.create_user(
            username="alice",
            email="alice@example.com",
            password="alice-password-1",
            role="member",
        )
        print(f"  Created user: {member.username} (id={member.id})")
    except Exception as exc:
        print(f"  Skipping member user (already exists?): {exc}")
        member = user_svc.get_user_by_username("alice")

    if admin is None or member is None:
        print("ERROR: Could not obtain seed users.")
        return 1

    # Create a sample project
    try:
        project = project_svc.create_project(
            name="Sample Project",
            description="A project created by the seed-data command.",
            owner_id=admin.id,  # type: ignore[arg-type]
            status="active",
            tags=["sample", "demo"],
        )
        print(f"  Created project: '{project.name}' (id={project.id})")
    except Exception as exc:
        print(f"  Skipping project (already exists?): {exc}")
        projects = project_svc.list_by_owner(admin.id)  # type: ignore[arg-type]
        project = projects[0] if projects else None

    if project is None:
        print("ERROR: Could not obtain seed project.")
        return 1

    # Create sample tasks
    for title, priority in [
        ("Set up repository", "high"),
        ("Write documentation", "medium"),
        ("Run initial tests", "low"),
    ]:
        try:
            task = task_svc.create_task(
                project_id=project.id,  # type: ignore[arg-type]
                title=title,
                description=f"Task: {title}",
                created_by=admin.id,  # type: ignore[arg-type]
                priority=priority,
                assignee_id=member.id,
            )
            print(f"  Created task: '{task.title}' (id={task.id})")
        except Exception as exc:
            print(f"  Skipping task '{title}': {exc}")

    print("Done.")
    return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    """Create a single user account from CLI arguments."""
    config, db = _bootstrap(getattr(args, "db", None))
    services = _build_services(config, db)
    user_svc: UserService = services["user"]

    try:
        user = user_svc.create_user(
            username=args.username,
            email=args.email,
            password=args.password,
            role=args.role,
        )
        print(json.dumps(user.to_dict(), indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_create_project(args: argparse.Namespace) -> int:
    """Create a project from CLI arguments."""
    config, db = _bootstrap(getattr(args, "db", None))
    services = _build_services(config, db)
    project_svc: ProjectService = services["project"]

    try:
        project = project_svc.create_project(
            name=args.name,
            description=args.description,
            owner_id=int(args.owner_id),
        )
        print(json.dumps(project.to_dict(), indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_run_tests(args: argparse.Namespace) -> int:
    """Print instructions for running the test suite."""
    print("To run the PyServiceLab test suite, execute:")
    print()
    print("    pytest -q")
    print()
    print("Ensure you have installed the dev dependencies first:")
    print("    pip install -e '.[dev]'")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pyservicelab.cli",
        description="PyServiceLab command-line interface",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite database path (overrides PYSERVICELAB_DB env var)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # show-config
    subparsers.add_parser("show-config", help="Display the current configuration")

    # seed-data
    subparsers.add_parser("seed-data", help="Populate the database with sample data")

    # run-tests
    subparsers.add_parser("run-tests", help="Show instructions for running tests")

    # create-user
    p_user = subparsers.add_parser("create-user", help="Create a new user account")
    p_user.add_argument("--username", required=True, help="Login username")
    p_user.add_argument("--email", required=True, help="Email address")
    p_user.add_argument("--password", required=True, help="Plaintext password")
    p_user.add_argument(
        "--role",
        default="member",
        choices=["admin", "manager", "member", "guest"],
        help="User role (default: member)",
    )

    # create-project
    p_project = subparsers.add_parser("create-project", help="Create a new project")
    p_project.add_argument("--name", required=True, help="Project name")
    p_project.add_argument("--description", default="", help="Project description")
    p_project.add_argument("--owner-id", required=True, dest="owner_id", help="Owner user ID")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """Parse arguments and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch: dict = {
        "show-config": cmd_show_config,
        "seed-data": cmd_seed_data,
        "run-tests": cmd_run_tests,
        "create-user": cmd_create_user,
        "create-project": cmd_create_project,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
