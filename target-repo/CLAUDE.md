# Claude Project Rules – PyServiceLab

This project is a benchmark repository used for evaluating agentic AI systems.

Claude must follow these rules strictly:

---

## 1. Code Quality Rules

- Python 3.11+
- Use type hints everywhere possible
- Use clear docstrings
- Keep files modular and readable
- Avoid overly clever or complex patterns
- No network calls
- No unnecessary dependencies

---

## 2. Testing Rules

- Use pytest
- All tests must pass before finishing
- Tests must be deterministic
- Use temporary SQLite databases in tests
- Avoid randomness unless seeded

---

## 3. Architecture Rules

- Clean separation between:
  - domain
  - services
  - db layer
  - auth layer
  - security layer
  - config layer
- CLI must use service layer (not directly access DB)
- Avoid circular imports

---

## 4. Project Size

- Target approximately 4,000 total lines of Python code
- Prefer many moderate-sized files over huge files
- Tests included in total LOC

---

## 5. Completion Checklist

Before stopping, Claude must:

1. Ensure file structure matches PRD.md
2. Generate pyproject.toml
3. Generate README.md with setup instructions
4. Confirm `pytest -q` passes
5. Confirm CLI commands execute without crashing