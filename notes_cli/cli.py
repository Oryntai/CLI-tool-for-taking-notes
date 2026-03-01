from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

from .config import load_config, parse_backend, save_config
from .editor import edit_note_in_editor
from .formatting import note_detail, notes_table, parse_tags, truncate
from .storage import MISSING, JSONBackend, NotesBackend, SQLiteBackend

app = typer.Typer(help="Local notes CLI with SQLite/JSON backends.")


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _backend_from_config() -> tuple[NotesBackend, Path, str]:
    cfg = load_config()
    if cfg.backend == "sqlite":
        return SQLiteBackend(cfg.sqlite_path), cfg.data_dir, cfg.backend
    return JSONBackend(cfg.json_path), cfg.data_dir, cfg.backend


def _require_backend() -> NotesBackend:
    backend, _, _ = _backend_from_config()
    if not backend.is_initialized():
        _fail("Storage is not initialized. Run `notes init` first.")
    return backend


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
    backend_impl: NotesBackend
    if cfg.backend == "sqlite":
        backend_impl = SQLiteBackend(cfg.sqlite_path)
    else:
        backend_impl = JSONBackend(cfg.json_path)

    backend_impl.initialize()
    typer.echo(f"Initialized {cfg.backend} backend in: {cfg.data_dir}")


@app.command()
def info(
    format: str = typer.Option("text", "--format", help="text or json"),
) -> None:
    """Show current backend, paths, and basic note stats."""
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

    typer.echo(f"Backend: {payload['backend']}")
    typer.echo(f"Data dir: {payload['data_dir']}")
    typer.echo(f"Initialized: {'yes' if initialized else 'no'}")
    typer.echo(
        "Notes: "
        f"total={payload['total_notes']}, "
        f"active={payload['active_notes']}, "
        f"archived={payload['archived_notes']}, "
        f"pinned={payload['pinned_notes']}"
    )


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

    archived_mode = "all" if all_notes else "archived" if archived else "active"

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


@app.command("import")
def import_notes(
    in_file: Path = typer.Option(
        ...,
        "--in",
        exists=True,
        dir_okay=False,
        help="Source .json file",
    ),
    mode: str = typer.Option("skip", "--mode", help="skip or overwrite for duplicate ids"),
) -> None:
    """Import notes from JSON file."""
    backend = _require_backend()
    mode_clean = mode.strip().lower()
    if mode_clean not in {"skip", "overwrite"}:
        _fail("--mode must be one of: skip, overwrite.")

    try:
        payload = json.loads(in_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"Invalid JSON input: {exc}")

    if isinstance(payload, dict) and "notes" in payload:
        payload = payload["notes"]

    if not isinstance(payload, list):
        _fail("Import file must contain a JSON array of notes.")

    try:
        inserted, updated, skipped = backend.import_notes(
            payload,
            mode=mode_clean,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        _fail(str(exc))

    typer.echo(f"Import done: inserted={inserted}, updated={updated}, skipped={skipped}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
