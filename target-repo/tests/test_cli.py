"""Tests for the CLI entry points."""
from __future__ import annotations

import json
import sys
from unittest.mock import patch

import pytest

from pyservicelab.cli import (
    build_parser,
    cmd_run_tests,
    cmd_show_config,
    main,
)


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_parser_exists(self) -> None:
        parser = build_parser()
        assert parser is not None

    def test_parser_has_show_config(self) -> None:
        parser = build_parser()
        # Should not raise
        args = parser.parse_args(["show-config"])
        assert args.command == "show-config"

    def test_parser_has_seed_data(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["seed-data"])
        assert args.command == "seed-data"

    def test_parser_has_run_tests(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run-tests"])
        assert args.command == "run-tests"

    def test_parser_create_user_requires_args(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["create-user"])  # missing required args

    def test_parser_create_user_with_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "create-user",
            "--username", "myuser",
            "--email", "myuser@example.com",
            "--password", "mypassword",
        ])
        assert args.username == "myuser"
        assert args.email == "myuser@example.com"
        assert args.role == "member"  # default

    def test_parser_create_project_with_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "create-project",
            "--name", "My Project",
            "--owner-id", "1",
        ])
        assert args.name == "My Project"
        assert args.owner_id == "1"


# ---------------------------------------------------------------------------
# Command: show-config
# ---------------------------------------------------------------------------


class TestShowConfig:
    def test_show_config_exits_zero(self, capsys: pytest.CaptureFixture) -> None:
        code = main(["show-config"])
        assert code == 0

    def test_show_config_outputs_json(self, capsys: pytest.CaptureFixture) -> None:
        main(["show-config"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "settings" in data
        assert "feature_flags" in data

    def test_show_config_masks_secret(self, capsys: pytest.CaptureFixture) -> None:
        main(["show-config"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["settings"]["secret_key"] == "***"


# ---------------------------------------------------------------------------
# Command: run-tests
# ---------------------------------------------------------------------------


class TestRunTests:
    def test_run_tests_exits_zero(self, capsys: pytest.CaptureFixture) -> None:
        code = main(["run-tests"])
        assert code == 0

    def test_run_tests_outputs_instructions(self, capsys: pytest.CaptureFixture) -> None:
        main(["run-tests"])
        captured = capsys.readouterr()
        assert "pytest" in captured.out


# ---------------------------------------------------------------------------
# Command: seed-data
# ---------------------------------------------------------------------------


class TestSeedData:
    def test_seed_data_exits_zero(self, capsys: pytest.CaptureFixture) -> None:
        # Use in-memory DB to avoid side effects
        code = main(["--db", ":memory:", "seed-data"])
        assert code == 0

    def test_seed_data_creates_users(self, capsys: pytest.CaptureFixture) -> None:
        main(["--db", ":memory:", "seed-data"])
        captured = capsys.readouterr()
        assert "admin" in captured.out or "alice" in captured.out


# ---------------------------------------------------------------------------
# Command: create-user
# ---------------------------------------------------------------------------


class TestCreateUser:
    def test_create_user_exits_zero(self, capsys: pytest.CaptureFixture) -> None:
        code = main([
            "--db", ":memory:",
            "create-user",
            "--username", "cliuser",
            "--email", "cliuser@example.com",
            "--password", "CliPass1!",
        ])
        assert code == 0

    def test_create_user_outputs_json(self, capsys: pytest.CaptureFixture) -> None:
        main([
            "--db", ":memory:",
            "create-user",
            "--username", "jsonuser",
            "--email", "jsonuser@example.com",
            "--password", "JsonPass1!",
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["username"] == "jsonuser"

    def test_create_user_invalid_email_exits_nonzero(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        code = main([
            "--db", ":memory:",
            "create-user",
            "--username", "bademail",
            "--email", "not-an-email",
            "--password", "ValidPass1!",
        ])
        assert code != 0


# ---------------------------------------------------------------------------
# Command: create-project
# ---------------------------------------------------------------------------


class TestCreateProject:
    def _create_and_get_user_id(self, capsys: pytest.CaptureFixture) -> int:
        """Helper: create a user via CLI and return its id."""
        main([
            "--db", ":memory:",
            "create-user",
            "--username", "projowner",
            "--email", "projowner@example.com",
            "--password", "ProjPass1!",
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        return data["id"]

    def test_create_project_invalid_owner_exits_nonzero(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        code = main([
            "--db", ":memory:",
            "create-project",
            "--name", "My Project",
            "--owner-id", "99999",
        ])
        assert code != 0
