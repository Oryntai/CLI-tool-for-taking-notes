# Roadmap

This roadmap reflects likely next steps for Notes CLI.

## Near Term

- Improve CLI output polish for large datasets (pagination/offset).
- Expand test coverage around failure modes and import edge cases.
- Add explicit data format validation for backups and imports.
- Publish a terminal demo (GIF or asciinema) and link it in README.

## Mid Term

- Introduce schema migration strategy for SQLite.
- Improve search performance for larger note collections.
- Add richer metadata support for notes (for example source labels or reminders).
- Improve user docs with workflow-oriented guides in `docs/`.

## Long Term

- Optional shell completion and packaged binaries.
- Optional plugin/hooks system for automation.
- Optional encrypted storage mode.

## Non-Goals (for now)

- Cloud sync as a required dependency.
- Multi-user shared backend.
