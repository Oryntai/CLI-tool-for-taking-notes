# Notes CLI

Fast local-first command-line notes app with SQLite and JSON backends.

[![CI](https://github.com/Oryntai/CLI-tool-for-taking-notes/actions/workflows/ci.yml/badge.svg)](https://github.com/Oryntai/CLI-tool-for-taking-notes/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-0A7EA4)
![Storage](https://img.shields.io/badge/storage-SQLite%20%2B%20JSON-4C9A2A)
![License](https://img.shields.io/badge/license-MIT-green)

## Demo

Quick terminal flow:

```bash
notes init
notes add "Draft architecture notes" --title "Design" --tags dev,ideas --pin
notes add --stdin --title "Inbox" << EOF
Need to benchmark SQLite queries.
EOF
notes list
notes search benchmark
notes backup --out backup/notes.json.gz --compress
```

For a richer terminal recording, see `docs/demo-plan.md` and publish an asciinema/GIF.

## Why This Project

`notes` is built for developers who want notes that are:

- Offline by default
- Fast to query from a terminal
- Easy to back up and restore
- Portable across Windows, macOS, and Linux

No external service, no account, no lock-in.

## Features

- `notes init` with `sqlite` or `json`
- Add from argument, `--body`, or `--stdin`
- Filter/list by tags, pinned, archived/all
- Search in title/body with optional tag filters
- Edit in flags or external editor (`$EDITOR`)
- Safe delete with confirmation (`--yes` to skip)
- JSON export/import and backup/restore
- Diagnostics and config commands (`info`, `recent`, `doctor`, `config`)

## Quick Start

### Install for development

```bash
python -m pip install -e ".[dev]"
```

### Initialize storage

```bash
notes init
```

### Add and read notes

```bash
notes add "Hello terminal notes" --tags demo
notes list
notes view 1
```

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

## Daily Workflows

### Inbox capture

```bash
notes add --stdin --title "Inbox" --tags inbox
```

### Prioritized list

```bash
notes list --pinned
notes pin 12
```

### Backup before risky edits

```bash
notes backup --out backups/notes-$(date +%Y%m%d).json.gz --compress
```

## Storage Layout

Default root:

- Linux/macOS: `~/.local/share/notes-cli/`
- Windows: `%APPDATA%\\notes-cli\\`

Files:

- `config.json` runtime config
- `notes.db` SQLite backend
- `notes.json` JSON backend

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
|-- CHANGELOG.md
|-- ROADMAP.md
`-- README.md
```

## Quality Checks

```bash
ruff check .
mypy notes_cli
pytest --cov=notes_cli --cov-report=term-missing --cov-fail-under=70
pip-audit
```

## Docker

```bash
docker build -t notes-cli .
docker run --rm -it -v notes_data:/data notes-cli init
docker run --rm -it -v notes_data:/data notes-cli add "Hello from Docker"
docker run --rm -it -v notes_data:/data notes-cli list
```

## Contributing

See `CONTRIBUTING.md` for setup and guidelines.

## Community

- Code of Conduct: `CODE_OF_CONDUCT.md`
- Security policy: `SECURITY.md`

## Roadmap and Releases

- Planned features: `ROADMAP.md`
- Release history: `CHANGELOG.md`

## License

MIT. See `LICENSE`.
