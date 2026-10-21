# Contributing

Contributions are welcome. Please keep changes focused and include tests for behavior changes, especially in patch parsing, path checks, rollback, privacy, and subprocess handling.

## Development setup

Use Python 3.10 or newer:

```bash
python -m venv .venv
# Activate the environment, then:
python -m pip install -e '.[dev,dashboard]'
```

The automated suite mocks Ollama and Discord; it does not need a model or webhook. Before opening a pull request, run:

```bash
pytest
ruff check src tests
python -m build
```

## Safety and privacy

- Do not include real tracebacks, credentials, webhook URLs, databases, or local logs in test fixtures.
- Do not make external reporting the default.
- Patch changes must preserve explicit review, exact source matching, and rollback behavior.
- Do not describe subprocess execution as a security sandbox.
- Document any new data sent to Ollama, Discord, or another external service.

## Pull requests

Explain the user-visible behavior, the checks you ran, and any checks that need a real local service. Keep documentation and the CLI help aligned with the implementation.
