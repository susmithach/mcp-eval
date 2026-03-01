# PyServiceLab

A medium-sized Python service repository designed as a benchmark dataset for
evaluating agentic AI systems (prompt-based, RAG-based, and MCP-based).

---

## Features

- **Authentication** – PBKDF2 password hashing, HMAC-signed tokens, role-based policies
- **User / Project / Task management** – full CRUD with validation and audit logging
- **Audit log** – every state-changing operation is recorded
- **Configuration** – environment-variable driven settings and feature flags
- **Security helpers** – sanitization, safe path resolution, SQL-injection and XSS detection
- **CLI** – five commands available via `python -m pyservicelab.cli`
- **Tests** – deterministic pytest suite (~4 000 LOC total)

---

## Project Structure

```
target-repo/
  pyservicelab/
    cli.py
    config/           settings, feature_flags, loaders
    core/             errors, logging, tracing, validation, utils, text, time
    auth/             hashing, tokens, models, service, policies
    db/               sqlite, migrations, repo_base, user/project/task/audit repos
    domain/           user, project, task, audit
    services/         user, project, task, audit services
    security/         sanitization, safe_paths, secrets, checks
    api/              schemas, handlers, routing
  tests/
    conftest.py
    test_auth.py
    test_users.py
    test_projects.py
    test_tasks.py
    test_config.py
    test_security.py
    test_audit.py
    test_cli.py
  pyproject.toml
  README.md
```

---

## Setup

### Requirements

- Python 3.11+
- No external runtime dependencies (pure stdlib)

### Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows
```

### Install the project

```bash
pip install -e ".[dev]"
```

---

## Running Tests

```bash
pytest -q
```

All tests use in-memory SQLite databases and are fully deterministic.

---

## CLI Usage

```bash
# Show current configuration
python -m pyservicelab.cli show-config

# Populate the database with sample data
python -m pyservicelab.cli --db /tmp/demo.db seed-data

# Create a user
python -m pyservicelab.cli --db /tmp/demo.db create-user \
  --username alice \
  --email alice@example.com \
  --password "AlicePass1!"

# Create a project (requires an existing owner user id)
python -m pyservicelab.cli --db /tmp/demo.db create-project \
  --name "My Project" \
  --description "A great project" \
  --owner-id 1

# Show instructions for running the test suite
python -m pyservicelab.cli run-tests
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PYSERVICELAB_DB` | `:memory:` | SQLite database path |
| `PYSERVICELAB_SECRET` | `dev-secret-key-please-change` | HMAC signing secret (≥ 16 chars) |
| `PYSERVICELAB_TOKEN_EXPIRY` | `3600` | Token lifetime in seconds |
| `PYSERVICELAB_LOG_LEVEL` | `INFO` | Logging verbosity |
| `PYSERVICELAB_DEBUG` | `false` | Enable debug mode |

---

## Architecture

```
CLI ──► API handlers ──► Services ──► Repositories ──► SQLite
                                └──► Auth service
                                └──► Audit service
```

- **Domain** models are plain Python dataclasses with no persistence logic.
- **Repositories** handle all SQL; they accept and return domain models.
- **Services** contain business logic; they depend on repositories and each other.
- **CLI** uses services only – never touches the database directly.
- **Security** helpers are stateless functions; no circular dependencies.

---

## Task Injection Framework

The `tasks/` directory contains `.patch` files that introduce controlled bugs for
use in AI evaluation benchmarks.  Each patch corresponds to one or more specific
failing tests so results are deterministic.

### Apply a task

```bash
python scripts/apply_task.py task_01_token_expiry_bypass
```

The script validates that the working tree is clean before applying the patch and
prints the test(s) expected to fail afterwards.

### Run the failing test(s)

```bash
pytest tests/test_auth.py::TestTokens::test_decode_expired_token
```

### Reset to clean baseline

```bash
python scripts/reset_repo.py
```

Discards all uncommitted changes to tracked files.  Run `pytest -q` to confirm
all tests pass again.

### Available tasks

| Task file | Bug introduced | Failing test(s) |
|---|---|---|
| `task_01_token_expiry_bypass.patch` | Expiry check removed from `decode_token` | `test_auth.py::TestTokens::test_decode_expired_token` |
| `task_02_project_tags_inverted.patch` | `get_tags()` condition inverted so only blank tokens are returned | `test_projects.py::TestProjectTags::test_create_with_tags`, `test_update_tags` |
| `task_03_empty_name_accepted.patch` | Empty-value guard removed from `validate_non_empty` | `test_projects.py::TestCreateProject::test_create_empty_name_raises`, `test_tasks.py::TestCreateTask::test_create_empty_title_raises` |
| `task_04_audit_count_broken.patch` | `AuditService.count()` always returns `0` | `test_audit.py::TestAuditService::test_count_total` |
| `task_05_email_exists_always_false.patch` | `UserRepository.email_exists()` always returns `False` | `test_users.py::TestCreateUser::test_create_duplicate_email_raises`, `test_auth.py::TestRegister::test_register_duplicate_email_raises` |

---

## License

MIT
