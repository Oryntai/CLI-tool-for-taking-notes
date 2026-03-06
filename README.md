# Notes CLI

Local-first, cross-platform command-line notes app with SQLite by default and optional JSON storage.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-0A7EA4)
![Storage](https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-4C9A2A)
![License](https://img.shields.io/badge/license-MIT-green)

## Why This Project

`notes` is designed for speed and reliability in terminal workflows:

- Fully offline, no external services
- Fast CRUD operations and search
- Tags, pinned notes, archive mode
- JSON import/export + backup/restore
- Config management and diagnostics commands
- Works on Windows, macOS, Linux
- CI-ready with lint, tests, type checks, coverage, and security audit

## Core Features

- `notes init` with `sqlite` or `json` backend
- Add note from argument, `--body`, or `--stdin`
- List/filter by tags, pinned, archived/all
- View full note in text or JSON
- Search by substring in title/body + tag filters
- Tag analytics with usage frequency (`notes tags`)
- Edit via flags or external editor (`$EDITOR`, fallback `nano/notepad`)
- Archive/unarchive and pin/unpin
- Safe delete with confirmation (`--yes` to skip)
- Export/import notes to JSON with duplicate handling (`skip|overwrite`)
- `notes backup` / `notes restore` for portable backups
- `notes info`, `notes recent`, `notes doctor` for operational visibility
- `notes config show|get|set|reset` for runtime config management

## Quick Demo

```bash
notes init
notes add "Draft architecture notes" --title "Design" --tags dev,ideas --pin
notes add --stdin --title "Inbox" << EOF
Need to benchmark SQLite queries.
EOF
notes recent
notes tags --all --limit 5
notes doctor
notes backup --out backup/notes.json.gz --compress
```

## Installation

### Local Development Install

```bash
python -m pip install -e ".[dev]"
```

You can run the app as `notes` or `python -m notes_cli`.

### Quality Checks

```bash
ruff check .
mypy notes_cli
pytest --cov=notes_cli --cov-report=term-missing --cov-fail-under=70
pip-audit
```

## Docker Deployment

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
notes recent [--limit N] [--format table|json]
notes doctor [--format text|json]

notes add "body" [--title TITLE] [--tags a,b] [--pin]
notes add --title TITLE --body BODY
notes add --stdin
notes list [--limit N] [--tag TAG] [--pinned] [--archived|--all] [--format table|json]
notes tags [--limit N] [--archived|--all] [--format table|json]
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
notes backup --out backup.json[.gz] [--compress]
notes restore --in backup.json[.gz] [--mode skip|overwrite] [--yes]

notes config show [--format text|json]
notes config get backend|data_dir|home_dir|config_file|config_exists
notes config set backend|data_dir <value> [--init-storage]
notes config reset [--yes]
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
|-- notes_cli/
|   |-- cli.py
|   |-- storage.py
|   |-- editor.py
|   |-- formatting.py
|   |-- config.py
|   `-- models.py
|-- tests/
|   `-- test_cli.py
|-- .github/workflows/
|   `-- ci.yml
|-- Dockerfile
|-- pyproject.toml
`-- README.md
```

## CI

GitHub Actions pipeline includes:

- Lint (`ruff`)
- Type checking (`mypy`)
- Tests + coverage gate (`pytest-cov`, fail-under 70%)
- Docker image build
- Dependency security audit (`pip-audit`, non-blocking)

## License

MIT. See [LICENSE](LICENSE).
