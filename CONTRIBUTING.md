# Contributing

Thanks for considering a contribution.

## Development Setup

```bash
python -m pip install -e ".[dev]"
```

## Validate Changes

```bash
ruff check .
mypy notes_cli
pytest
pip-audit
```

## Contribution Guidelines

- Keep the CLI UX consistent and predictable
- Preserve offline-first behavior
- Add tests for behavioral changes
- Update README when user-facing commands change
- Keep code cross-platform (Windows/macOS/Linux)

## Pull Requests

- Use a focused PR scope
- Describe the user-visible impact
- Include test evidence (`pytest`, `ruff`, `mypy`)
