from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from .formatting import parse_tags
from .models import Note

_DELIMITER = "---"


def _editor_command() -> str:
    from_env = os.getenv("EDITOR", "").strip()
    if from_env:
        return from_env
    return "notepad" if os.name == "nt" else "nano"


def _serialize(note: Note) -> str:
    header = [f"title: {note.title or ''}", f"tags: {','.join(note.tags)}", _DELIMITER]
    return "\n".join([*header, note.body]) + "\n"


def _parse(content: str) -> tuple[str | None, list[str], str]:
    lines = content.splitlines()
    try:
        divider_idx = lines.index(_DELIMITER)
    except ValueError as exc:
        raise ValueError("Edited note must contain '---' divider.") from exc

    header = lines[:divider_idx]
    body = "\n".join(lines[divider_idx + 1 :]).strip()
    if not body:
        raise ValueError("Body must not be empty after editing.")

    title: str | None = None
    tags: list[str] = []

    for line in header:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "title":
            title = value or None
        elif key == "tags":
            tags = parse_tags(value)

    return title, tags, body


def edit_note_in_editor(note: Note) -> tuple[str | None, list[str], str]:
    initial = _serialize(note)
    tmp_path: Path

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tmp:
        tmp.write(initial)
        tmp_path = Path(tmp.name)

    editor_cmd = _editor_command()
    cmd = shlex.split(editor_cmd, posix=os.name != "nt")
    cmd.append(str(tmp_path))

    try:
        subprocess.run(cmd, check=True)
        edited_content = tmp_path.read_text(encoding="utf-8")
        return _parse(edited_content)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
