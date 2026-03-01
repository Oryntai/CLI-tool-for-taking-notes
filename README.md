# Notes CLI

Local-first, cross-platform command-line notes app with SQLite by default and optional JSON storage.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-0A7EA4)
![Storage](https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-4C9A2A)
![Tests](https://img.shields.io/badge/tests-21%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

## Why This Project

`notes` is designed for speed and reliability in terminal workflows:

- Fully offline, no external services
- Fast CRUD operations and search
- Tags, pinned notes, archive mode
- JSON import/export for backup and migration
- Works on Windows, macOS, Linux
- Ready for CI and Docker deployment

## Core Features

- `notes init` with `sqlite` or `json` backend
- Add note from argument, `--body`, or `--stdin`
- List/filter by tags, pinned, archived/all
- View full note in text or JSON
- Search by substring in title/body + tag filters
- Edit via flags or external editor (`$EDITOR`, fallback `nano/notepad`)
- Archive/unarchive and pin/unpin
- Safe delete with confirmation (`--yes` to skip)
- Export/import notes to JSON with duplicate handling (`skip|overwrite`)
- `notes info` for backend/path/stats overview

## Quick Demo

```bash
notes init
notes add "Draft architecture notes" --title "Design" --tags dev,ideas --pin
notes add --stdin --title "Inbox" << EOF
Need to benchmark SQLite queries.
EOF
notes list
notes search sqlite --format json
notes view 1
notes export --out backup/notes.json
```

## Installation

### Local Development Install

```bash
python -m pip install -e ".[dev]"
```

You can run the app as `notes` or `python -m notes_cli`.

### Run Quality Checks

```bash
ruff check .
pytest
```

## Docker Deployment

The repository includes a production-ready `Dockerfile`.

### Build Image

```bash
docker build -t notes-cli .
```

### Initialize Storage

```bash
docker run --rm -it -v notes_data:/data notes-cli init
```

### Create and List Notes

```bash
docker run --rm -it -v notes_data:/data notes-cli add "Hello from Docker" --tags demo
docker run --rm -it -v notes_data:/data notes-cli list
```

Container defaults:

- data directory: `/data`
- environment variable: `NOTES_CLI_HOME=/data`
- non-root runtime user

## Command Reference

```bash
notes --help
notes init --backend sqlite|json [--path PATH]
notes info [--format text|json]
notes add "body" [--title TITLE] [--tags a,b] [--pin]
notes add --title TITLE --body BODY
notes add --stdin
notes list [--limit N] [--tag TAG] [--pinned] [--archived|--all] [--format table|json]
notes view <id> [--format text|json]
notes search <query> [--tag TAG] [--format table|json]
notes edit <id> [--title TITLE] [--body BODY] [--tags a,b]
notes archive <id>
notes unarchive <id>
notes pin <id>
notes unpin <id>
notes delete <id> [--yes]
notes export --out notes.json
notes import --in notes.json [--mode skip|overwrite]
```

## Storage Layout

Default storage root:

- Linux/macOS: `~/.local/share/notes-cli/`
- Windows: `%APPDATA%\\notes-cli\\`

Files in storage directory:

- `config.json` for selected backend and data path
- `notes.db` for SQLite backend
- `notes.json` for JSON backend

SQLite keeps tags as JSON text in the `notes.tags` column.

## Project Structure

```text
.
├── notes_cli/
│   ├── cli.py          # Typer commands
│   ├── storage.py      # SQLite + JSON backends
│   ├── editor.py       # External editor workflow
│   ├── formatting.py   # Table/text rendering
│   ├── config.py       # Runtime config and paths
│   └── models.py       # Note model
├── tests/
│   └── test_cli.py     # Integration-style CLI tests
├── .github/workflows/
│   └── ci.yml          # Lint + tests on Ubuntu/Windows
└── Dockerfile
```

## CI

GitHub Actions pipeline runs:

- `ruff check .`
- `pytest`
- matrix on `ubuntu-latest` and `windows-latest`

## License

MIT. See [LICENSE](LICENSE).
