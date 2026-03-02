from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

import typer

from .config import (
    config_exists,
    load_config,
    parse_backend,
    read_raw_config,
    reset_config,
    save_config,
)
from .editor import edit_note_in_editor
from .formatting import (
    key_value_table,
    note_detail,
    notes_table,
    parse_tags,
    render_table,
    truncate,
)
from .models import now_iso
from .storage import MISSING, JSONBackend, ListMode, NotesBackend, SQLiteBackend

app = typer.Typer(help="Local notes CLI with SQLite/JSON backends.")
config_app = typer.Typer(help="Manage notes CLI runtime configuration.")
app.add_typer(config_app, name="config")


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _backend_for_config(cfg) -> NotesBackend:
    if cfg.backend == "sqlite":
        return SQLiteBackend(cfg.sqlite_path)
    return JSONBackend(cfg.json_path)


def _backend_from_config() -> tuple[NotesBackend, Path, str]:
    cfg = load_config()
    return _backend_for_config(cfg), cfg.data_dir, cfg.backend


def _require_backend() -> NotesBackend:
    backend, _, _ = _backend_from_config()
    if not backend.is_initialized():
        _fail("Storage is not initialized. Run `notes init` first.")
    return backend


def _read_json_payload(path: Path) -> object:
    try:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                return json.loads(stream.read())

        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Failed to read '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input: {exc}") from exc


def _extract_note_list(payload: object) -> list[dict]:
    if isinstance(payload, dict) and "notes" in payload:
        payload = payload["notes"]

    if not isinstance(payload, list):
        raise ValueError("Input must contain a JSON array of notes.")

    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Import item #{idx} is not an object.")

    return cast(list[dict], payload)


def _parse_mode(mode: str) -> str:
    mode_clean = mode.strip().lower()
    if mode_clean not in {"skip", "overwrite"}:
        _fail("--mode must be one of: skip, overwrite.")
    return mode_clean


@app.command()
def init(
    backend: str = typer.Option("sqlite", "--backend", help="sqlite or json"),
    path: Path | None = typer.Option(None, "--path", help="Custom data directory"),
) -> None:
    """Initialize storage and persist runtime config."""
    try:
        backend_kind = parse_backend(backend)
    except ValueError as exc:
        _fail(str(exc))

    current = load_config()
    target_dir = path.expanduser().resolve() if path else current.data_dir

    cfg = save_config(backend=backend_kind, data_dir=target_dir)
    backend_impl = _backend_for_config(cfg)
    backend_impl.initialize()

    typer.echo(f"Initialized {cfg.backend} backend in: {cfg.data_dir}")


@app.command()
def info(
    format: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Show current backend, paths, and basic note stats."""
    cfg = load_config()
    backend, data_dir, backend_name = _backend_from_config()
    initialized = backend.is_initialized()

    total = 0
    archived = 0
    pinned = 0
    if initialized:
        notes = backend.export_notes()
        total = len(notes)
        archived = sum(1 for note in notes if note.archived)
        pinned = sum(1 for note in notes if note.pinned)

    payload = {
        "backend": backend_name,
        "data_dir": str(data_dir),
        "home_dir": str(cfg.home_dir),
        "config_file": str(cfg.config_file),
        "config_exists": config_exists(),
        "initialized": initialized,
        "total_notes": total,
        "active_notes": total - archived,
        "archived_notes": archived,
        "pinned_notes": pinned,
    }

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if fmt != "text":
        _fail("--format must be one of: text, json.")

    rows = [
        ("backend", str(payload["backend"])),
        ("data_dir", str(payload["data_dir"])),
        ("home_dir", str(payload["home_dir"])),
        ("config_file", str(payload["config_file"])),
        ("config_exists", "yes" if payload["config_exists"] else "no"),
        ("initialized", "yes" if initialized else "no"),
        ("total_notes", str(payload["total_notes"])),
        ("active_notes", str(payload["active_notes"])),
        ("archived_notes", str(payload["archived_notes"])),
        ("pinned_notes", str(payload["pinned_notes"])),
    ]
    typer.echo(key_value_table(rows))


@app.command()
def recent(
    limit: int = typer.Option(10, "--limit", help="Max notes to return"),
    format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    """Show recent active notes (shortcut for list)."""
    backend = _require_backend()
    notes = backend.list_notes(
        limit=max(limit, 0),
        tags=[],
        pinned_only=False,
        archived_mode="active",
    )

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps([note.to_dict() for note in notes], ensure_ascii=False, indent=2))
        return
    if fmt != "table":
        _fail("--format must be one of: table, json.")

    typer.echo(notes_table(notes))


@app.command()
def doctor(
    format: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Run diagnostics for config and storage health."""
    cfg = load_config()
    backend = _backend_for_config(cfg)

    checks: list[dict[str, str]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    add_check(
        "config_file",
        "OK" if config_exists() else "WARN",
        str(cfg.config_file) if config_exists() else "Config file missing (defaults in use)",
    )

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    probe = cfg.data_dir / ".notes-cli-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        add_check("data_dir_access", "OK", f"RW access to {cfg.data_dir}")
    except OSError as exc:
        add_check("data_dir_access", "FAIL", str(exc))

    if backend.is_initialized():
        storage_path = cfg.sqlite_path if cfg.backend == "sqlite" else cfg.json_path
        status = "OK" if storage_path.exists() else "FAIL"
        add_check("storage_file", status, str(storage_path))

        try:
            count = len(backend.export_notes())
            add_check("storage_read", "OK", f"Read succeeded, notes={count}")
        except (OSError, ValueError) as exc:
            add_check("storage_read", "FAIL", str(exc))
    else:
        add_check("storage_init", "WARN", "Storage is not initialized. Run `notes init`.")

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps(checks, ensure_ascii=False, indent=2))
    elif fmt == "text":
        rows = [[row["check"], row["status"], row["detail"]] for row in checks]
        typer.echo(render_table(["check", "status", "detail"], rows))
    else:
        _fail("--format must be one of: text, json.")

    if any(row["status"] == "FAIL" for row in checks):
        raise typer.Exit(code=1)


@app.command()
def add(
    body: str | None = typer.Argument(None, help="Note body as positional value"),
    title: str | None = typer.Option(None, "--title", help="Note title"),
    body_opt: str | None = typer.Option(None, "--body", help="Note body"),
    stdin: bool = typer.Option(False, "--stdin", help="Read note body from stdin"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    pin: bool = typer.Option(False, "--pin", help="Mark note as pinned"),
) -> None:
    """Create a note."""
    backend = _require_backend()

    if stdin:
        content = sys.stdin.read().strip()
    elif body_opt is not None:
        content = body_opt.strip()
    else:
        content = (body or "").strip()

    if not content:
        _fail("Note body is required (argument, --body, or --stdin).")

    try:
        note = backend.add_note(title=title, body=content, tags=parse_tags(tags), pinned=pin)
    except ValueError as exc:
        _fail(str(exc))

    preview = truncate(note.body.replace("\n", " ").strip(), 60)
    typer.echo(f"Created note {note.id}: {preview}")


@app.command("list")
def list_notes(
    limit: int = typer.Option(20, "--limit", help="Max notes to return"),
    tag: list[str] | None = typer.Option(None, "--tag", help="Filter by tag (repeatable)"),
    pinned: bool = typer.Option(False, "--pinned", help="Only pinned notes"),
    archived: bool = typer.Option(False, "--archived", help="Only archived notes"),
    all_notes: bool = typer.Option(False, "--all", help="Include archived and active"),
    format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    """List notes."""
    backend = _require_backend()

    fmt = format.strip().lower()
    if fmt not in {"table", "json"}:
        _fail("--format must be one of: table, json.")

    archived_mode: ListMode = "all" if all_notes else "archived" if archived else "active"

    notes = backend.list_notes(
        limit=max(limit, 0),
        tags=tag or [],
        pinned_only=pinned,
        archived_mode=archived_mode,
    )

    if fmt == "json":
        typer.echo(json.dumps([note.to_dict() for note in notes], ensure_ascii=False, indent=2))
        return

    typer.echo(notes_table(notes))


@app.command()
def view(
    note_id: int = typer.Argument(..., help="Note id"),
    format: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Show full note content."""
    backend = _require_backend()
    note = backend.get_note(note_id)
    if note is None:
        _fail(f"Note {note_id} not found.")

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps(note.to_dict(), ensure_ascii=False, indent=2))
        return
    if fmt != "text":
        _fail("--format must be one of: text, json.")

    typer.echo(note_detail(note))


@app.command()
def search(
    query: str = typer.Argument(..., help="Substring to search in title/body"),
    tag: list[str] | None = typer.Option(None, "--tag", help="Filter by tag (repeatable)"),
    format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    """Search notes by text and tags."""
    backend = _require_backend()
    notes = backend.search_notes(query=query, tags=tag or [])

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps([note.to_dict() for note in notes], ensure_ascii=False, indent=2))
        return
    if fmt != "table":
        _fail("--format must be one of: table, json.")

    typer.echo(notes_table(notes))


@app.command()
def edit(
    note_id: int = typer.Argument(..., help="Note id"),
    title: str | None = typer.Option(None, "--title", help="Replace title"),
    body: str | None = typer.Option(None, "--body", help="Replace body"),
    tags: str | None = typer.Option(None, "--tags", help="Replace comma-separated tags"),
) -> None:
    """Edit note directly via flags or in external editor."""
    backend = _require_backend()

    if title is None and body is None and tags is None:
        note = backend.get_note(note_id)
        if note is None:
            _fail(f"Note {note_id} not found.")

        try:
            next_title, next_tags, next_body = edit_note_in_editor(note)
            updated = backend.update_note(note_id, title=next_title, body=next_body, tags=next_tags)
        except subprocess.CalledProcessError as exc:
            _fail(f"Editor command failed with exit code {exc.returncode}.")
        except ValueError as exc:
            _fail(str(exc))

        if updated is None:
            _fail(f"Note {note_id} not found.")

        typer.echo(f"Updated note {updated.id}.")
        return

    title_value = MISSING if title is None else title
    body_value = MISSING if body is None else body
    tags_value = MISSING if tags is None else parse_tags(tags)

    try:
        updated = backend.update_note(
            note_id,
            title=title_value,
            body=body_value,
            tags=tags_value,
        )
    except ValueError as exc:
        _fail(str(exc))

    if updated is None:
        _fail(f"Note {note_id} not found.")

    typer.echo(f"Updated note {updated.id}.")


@app.command()
def archive(note_id: int = typer.Argument(..., help="Note id")) -> None:
    """Archive a note."""
    backend = _require_backend()
    updated = backend.update_note(note_id, archived=True)
    if updated is None:
        _fail(f"Note {note_id} not found.")
    typer.echo(f"Archived note {note_id}.")


@app.command()
def unarchive(note_id: int = typer.Argument(..., help="Note id")) -> None:
    """Restore an archived note."""
    backend = _require_backend()
    updated = backend.update_note(note_id, archived=False)
    if updated is None:
        _fail(f"Note {note_id} not found.")
    typer.echo(f"Unarchived note {note_id}.")


@app.command()
def pin(note_id: int = typer.Argument(..., help="Note id")) -> None:
    """Pin a note."""
    backend = _require_backend()
    updated = backend.update_note(note_id, pinned=True)
    if updated is None:
        _fail(f"Note {note_id} not found.")
    typer.echo(f"Pinned note {note_id}.")


@app.command()
def unpin(note_id: int = typer.Argument(..., help="Note id")) -> None:
    """Unpin a note."""
    backend = _require_backend()
    updated = backend.update_note(note_id, pinned=False)
    if updated is None:
        _fail(f"Note {note_id} not found.")
    typer.echo(f"Unpinned note {note_id}.")


@app.command()
def delete(
    note_id: int = typer.Argument(..., help="Note id"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Delete a note with confirmation unless --yes is used."""
    backend = _require_backend()

    if not yes:
        confirmed = typer.confirm(f"Delete note {note_id}?", default=False)
        if not confirmed:
            typer.echo("Canceled.")
            raise typer.Exit(code=0)

    deleted = backend.delete_note(note_id)
    if not deleted:
        _fail(f"Note {note_id} not found.")

    typer.echo(f"Deleted note {note_id}.")


@app.command("export")
def export_notes(
    out: Path = typer.Option(..., "--out", help="Destination .json file"),
) -> None:
    """Export all notes to JSON file."""
    backend = _require_backend()
    notes = backend.export_notes()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([note.to_dict() for note in notes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Exported {len(notes)} notes to {out}.")


@app.command("backup")
def backup_notes(
    out: Path = typer.Option(..., "--out", help="Destination .json or .gz file"),
    compress: bool = typer.Option(False, "--compress", help="Write gzip-compressed backup"),
) -> None:
    """Create portable backup with metadata."""
    backend = _require_backend()
    _, _, backend_name = _backend_from_config()
    notes = backend.export_notes()

    payload: dict[str, Any] = {
        "schema_version": 1,
        "exported_at": now_iso(),
        "backend": backend_name,
        "notes": [note.to_dict() for note in notes],
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    if compress or out.suffix.lower() == ".gz":
        with gzip.open(out, "wt", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
    else:
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    typer.echo(f"Backup created: {out} ({len(notes)} notes)")


@app.command("import")
def import_notes(
    in_file: Path = typer.Option(
        ...,
        "--in",
        exists=True,
        dir_okay=False,
        help="Source .json/.gz file",
    ),
    mode: str = typer.Option("skip", "--mode", help="skip or overwrite for duplicate ids"),
) -> None:
    """Import notes from JSON file."""
    backend = _require_backend()
    mode_clean = _parse_mode(mode)

    try:
        payload = _read_json_payload(in_file)
        notes_payload = _extract_note_list(payload)
        inserted, updated, skipped = backend.import_notes(notes_payload, mode=mode_clean)  # type: ignore[arg-type]
    except ValueError as exc:
        _fail(str(exc))

    typer.echo(f"Import done: inserted={inserted}, updated={updated}, skipped={skipped}")


@app.command("restore")
def restore_notes(
    in_file: Path = typer.Option(
        ...,
        "--in",
        exists=True,
        dir_okay=False,
        help="Backup file created by `notes backup`",
    ),
    mode: str = typer.Option("skip", "--mode", help="skip or overwrite for duplicate ids"),
    yes: bool = typer.Option(False, "--yes", help="Skip overwrite confirmation"),
) -> None:
    """Restore notes from backup file."""
    backend = _require_backend()
    mode_clean = _parse_mode(mode)

    if mode_clean == "overwrite" and not yes:
        confirmed = typer.confirm("Restore with overwrite mode?", default=False)
        if not confirmed:
            typer.echo("Canceled.")
            raise typer.Exit(code=0)

    try:
        payload = _read_json_payload(in_file)
        notes_payload = _extract_note_list(payload)
        inserted, updated, skipped = backend.import_notes(notes_payload, mode=mode_clean)  # type: ignore[arg-type]
    except ValueError as exc:
        _fail(str(exc))

    typer.echo(f"Restore done: inserted={inserted}, updated={updated}, skipped={skipped}")


@config_app.command("show")
def config_show(
    format: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Show effective runtime configuration."""
    payload = read_raw_config()
    fmt = format.strip().lower()

    if fmt == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if fmt != "text":
        _fail("--format must be one of: text, json.")

    rows = [(key, str(value)) for key, value in payload.items()]
    typer.echo(key_value_table(rows))


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="backend|data_dir|home_dir|config_file|config_exists"),
) -> None:
    """Get one runtime config value."""
    payload = read_raw_config()
    if key not in payload:
        _fail("Unknown key. Use: backend, data_dir, home_dir, config_file, config_exists.")

    typer.echo(str(payload[key]))


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="backend|data_dir"),
    value: str = typer.Argument(..., help="New value"),
    init_storage: bool = typer.Option(
        False,
        "--init-storage",
        help="Initialize storage after update",
    ),
) -> None:
    """Set backend or data directory."""
    current = load_config()

    if key == "backend":
        try:
            backend_kind = parse_backend(value)
        except ValueError as exc:
            _fail(str(exc))
        cfg = save_config(backend=backend_kind, data_dir=current.data_dir)
    elif key == "data_dir":
        cfg = save_config(backend=current.backend, data_dir=Path(value).expanduser().resolve())
    else:
        _fail("Unknown key. Use: backend or data_dir.")

    if init_storage:
        backend = _backend_for_config(cfg)
        backend.initialize()

    typer.echo(f"Updated config: backend={cfg.backend}, data_dir={cfg.data_dir}")


@config_app.command("reset")
def config_reset(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Delete config.json and fall back to defaults."""
    if not yes:
        confirmed = typer.confirm("Reset config file to defaults?", default=False)
        if not confirmed:
            typer.echo("Canceled.")
            raise typer.Exit(code=0)

    cfg = reset_config()
    typer.echo(f"Config reset. Default backend={cfg.backend}, data_dir={cfg.data_dir}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
