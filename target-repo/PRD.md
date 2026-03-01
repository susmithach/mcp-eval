# Product Requirements Document (PRD)

## Project Name: PyServiceLab

---

## 1. Purpose

PyServiceLab is a medium-sized Python service-style repository designed to serve as a benchmark dataset for evaluating agentic AI systems (Prompt-based, RAG-based, and MCP-based approaches).

The repository must:

- Run locally without internet.
- Have a deterministic and fully passing pytest suite.
- Contain realistic multi-module structure (~4,000 LOC total).
- Be suitable for introducing controlled bugs for experimental tasks.

---

## 2. Technical Constraints

- Python 3.11+
- SQLite for persistence (local file or temp DB in tests)
- No external APIs or network calls
- Minimal dependencies
- Deterministic test behavior (no flaky tests)
- Clean modular architecture
- Strong type hints and docstrings

---

## 3. Project Structure

target-repo/
  pyservicelab/
    __init__.py
    cli.py
    config/
      __init__.py
      settings.py
      feature_flags.py
      loaders.py
    core/
      __init__.py
      errors.py
      logging.py
      tracing.py
      validation.py
      utils.py
      text.py
      time.py
    auth/
      __init__.py
      hashing.py
      tokens.py
      models.py
      service.py
      policies.py
    db/
      __init__.py
      sqlite.py
      migrations.py
      repo_base.py
      user_repo.py
      project_repo.py
      task_repo.py
      audit_repo.py
    domain/
      __init__.py
      user.py
      project.py
      task.py
      audit.py
    services/
      __init__.py
      user_service.py
      project_service.py
      task_service.py
      audit_service.py
    security/
      __init__.py
      sanitization.py
      safe_paths.py
      secrets.py
      checks.py
    api/
      __init__.py
      schemas.py
      handlers.py
      routing.py
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


---

## 4. Functional Requirements

### 4.1 Authentication
- User registration
- Password hashing
- Token generation and validation
- Role-based basic policy enforcement

### 4.2 Project & Task Management
- CRUD operations for users, projects, and tasks
- Validation rules for data integrity
- Audit logging on state changes

### 4.3 Configuration
- Environment-based settings
- Feature flag support
- Config loading with validation

### 4.4 CLI Interface

Must support:
python -m pyservicelab.cli run-tests
python -m pyservicelab.cli seed-data
python -m pyservicelab.cli show-config
python -m pyservicelab.cli create-user
python -m pyservicelab.cli create-project


---

## 5. Test Requirements

- Use pytest
- All tests must pass
- Cover:
  - Authentication flows
  - CRUD logic
  - Security helpers
  - Config behavior
  - CLI behavior
- Tests must be deterministic

---

## 6. Non-Functional Requirements

- Approximately 4,000 total lines of Python code
- Well-structured modular code (avoid extremely large single files)
- Proper separation of concerns
- Clear docstrings
- Type hints

---

## 7. Acceptance Criteria

After generation:

1. Create virtual environment
2. Install project in editable mode
3. Run:

`pytest -q`


All tests must pass.

Also verify:

`python -m pyservicelab.cli show-config`

runs successfully.

---

## 8. Deliverables

- Fully implemented file structure
- Working pytest suite
- Valid pyproject.toml
- Clear README.md with setup instructions