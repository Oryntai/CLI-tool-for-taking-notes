# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog and Semantic Versioning principles.

## [Unreleased]

### Changed
- Improved repository presentation for GitHub (README refresh, roadmap, security and community docs).

## [0.1.0] - 2026-03-09

### Added
- Local-first notes CLI with Typer.
- SQLite and JSON storage backends.
- CRUD commands, search, tag analytics, pin/archive modes.
- Import/export and backup/restore workflows.
- Runtime configuration and diagnostics commands.
- Dockerfile and CI pipeline (lint, type check, tests, audit).

### Security
- Added dependency audit step via `pip-audit` in CI (non-blocking).
