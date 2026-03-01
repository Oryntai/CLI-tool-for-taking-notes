from __future__ import annotations

from collections.abc import Iterable

from .models import Note


def parse_tags(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    return text[: width - 3] + "..."


def _render_table(headers: list[str], rows: Iterable[list[str]]) -> str:
    rows_list = [headers, *list(rows)]
    widths = [max(len(row[idx]) for row in rows_list) for idx in range(len(headers))]

    def fmt(row: list[str]) -> str:
        return " | ".join(row[idx].ljust(widths[idx]) for idx in range(len(headers)))

    header_line = fmt(headers)
    divider = "-+-".join("-" * width for width in widths)
    body = "\n".join(fmt(row) for row in rows_list[1:])
    return f"{header_line}\n{divider}\n{body}" if body else f"{header_line}\n{divider}"


def notes_table(notes: list[Note]) -> str:
    headers = ["id", "title", "tags", "updated_at", "flags"]
    rows: list[list[str]] = []
    for note in notes:
        flags: list[str] = []
        if note.pinned:
            flags.append("pinned")
        if note.archived:
            flags.append("archived")

        rows.append(
            [
                str(note.id),
                truncate(note.title or "(no title)", 30),
                truncate(",".join(note.tags) if note.tags else "-", 25),
                note.updated_at,
                ",".join(flags) if flags else "-",
            ]
        )

    return _render_table(headers, rows)


def note_detail(note: Note) -> str:
    tags = ", ".join(note.tags) if note.tags else "-"
    lines = [
        f"ID: {note.id}",
        f"Title: {note.title or '(no title)'}",
        f"Tags: {tags}",
        f"Pinned: {'yes' if note.pinned else 'no'}",
        f"Archived: {'yes' if note.archived else 'no'}",
        f"Created: {note.created_at}",
        f"Updated: {note.updated_at}",
        "",
        note.body,
    ]
    return "\n".join(lines)
