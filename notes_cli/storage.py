from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Protocol

from .models import Note, now_iso

ListMode = Literal["active", "archived", "all"]
ImportMode = Literal["skip", "overwrite"]
MISSING = object()


def normalize_tags(raw_tags: Iterable[str] | None) -> list[str]:
    if raw_tags is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags:
        tag = raw.strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
    return normalized


def _match_tags(note_tags: list[str], required_tags: list[str]) -> bool:
    if not required_tags:
        return True
    note_set = {tag.casefold() for tag in note_tags}
    return all(tag.casefold() in note_set for tag in required_tags)


def _parse_import_item(item: object, *, index: int) -> Note:
    if not isinstance(item, dict):
        raise ValueError(f"Import item #{index} is not an object.")

    try:
        note = Note.from_dict(item)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Import item #{index} is invalid: {exc}") from exc

    if not note.body.strip():
        raise ValueError(f"Import item #{index} has empty body.")

    note.tags = normalize_tags(note.tags)
    return note


class NotesBackend(Protocol):
    def initialize(self) -> None: ...

    def is_initialized(self) -> bool: ...

    def add_note(self, *, title: str | None, body: str, tags: list[str], pinned: bool) -> Note: ...

    def get_note(self, note_id: int) -> Note | None: ...

    def list_notes(
        self,
        *,
        limit: int,
        tags: list[str],
        pinned_only: bool,
        archived_mode: ListMode,
    ) -> list[Note]: ...

    def search_notes(self, *, query: str, tags: list[str]) -> list[Note]: ...

    def update_note(
        self,
        note_id: int,
        *,
        title: str | None | object = MISSING,
        body: str | object = MISSING,
        tags: list[str] | object = MISSING,
        pinned: bool | object = MISSING,
        archived: bool | object = MISSING,
    ) -> Note | None: ...

    def delete_note(self, note_id: int) -> bool: ...

    def export_notes(self) -> list[Note]: ...

    def import_notes(self, notes: list[dict], *, mode: ImportMode) -> tuple[int, int, int]: ...


class SQLiteBackend:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    body TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def is_initialized(self) -> bool:
        return self.db_path.exists()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_note(self, row: sqlite3.Row) -> Note:
        tags_raw = row["tags"] or "[]"
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []

        return Note(
            id=int(row["id"]),
            title=row["title"],
            body=row["body"],
            tags=normalize_tags(tags),
            pinned=bool(row["pinned"]),
            archived=bool(row["archived"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def add_note(self, *, title: str | None, body: str, tags: list[str], pinned: bool) -> Note:
        body_clean = body.strip()
        if not body_clean:
            raise ValueError("Body must not be empty.")

        title_clean = title.strip() if isinstance(title, str) else None
        title_value = title_clean if title_clean else None
        tags_value = normalize_tags(tags)
        created_at = now_iso()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notes (title, body, tags, pinned, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title_value,
                    body_clean,
                    json.dumps(tags_value, ensure_ascii=False),
                    int(pinned),
                    0,
                    created_at,
                    created_at,
                ),
            )
            conn.commit()
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("Failed to obtain inserted note id.")
            note_id = int(row_id)

        return self.get_note(note_id)  # type: ignore[return-value]

    def get_note(self, note_id: int) -> Note | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_note(row)

    def list_notes(
        self,
        *,
        limit: int,
        tags: list[str],
        pinned_only: bool,
        archived_mode: ListMode,
    ) -> list[Note]:
        where: list[str] = []
        params: list[object] = []

        if pinned_only:
            where.append("pinned = 1")

        if archived_mode == "active":
            where.append("archived = 0")
        elif archived_mode == "archived":
            where.append("archived = 1")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        query = f"SELECT * FROM notes {where_sql} ORDER BY updated_at DESC, id DESC"

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        all_notes = [self._row_to_note(row) for row in rows]
        filtered = [note for note in all_notes if _match_tags(note.tags, tags)]
        return filtered[: max(limit, 0)]

    def search_notes(self, *, query: str, tags: list[str]) -> list[Note]:
        needle = f"%{query.casefold()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE archived = 0
                  AND (
                      lower(coalesce(title, '')) LIKE ?
                      OR lower(body) LIKE ?
                  )
                ORDER BY updated_at DESC, id DESC
                """,
                (needle, needle),
            ).fetchall()

        candidates = [self._row_to_note(row) for row in rows]
        return [note for note in candidates if _match_tags(note.tags, tags)]

    def update_note(
        self,
        note_id: int,
        *,
        title: str | None | object = MISSING,
        body: str | object = MISSING,
        tags: list[str] | object = MISSING,
        pinned: bool | object = MISSING,
        archived: bool | object = MISSING,
    ) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None:
            return None

        next_title = existing.title
        if title is not MISSING:
            if isinstance(title, str):
                clean = title.strip()
                next_title = clean if clean else None
            else:
                next_title = None

        next_body = existing.body
        if body is not MISSING:
            clean_body = str(body).strip()
            if not clean_body:
                raise ValueError("Body must not be empty.")
            next_body = clean_body

        next_tags = existing.tags
        if tags is not MISSING:
            next_tags = normalize_tags(tags if isinstance(tags, list) else [])

        next_pinned = existing.pinned if pinned is MISSING else bool(pinned)
        next_archived = existing.archived if archived is MISSING else bool(archived)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, body = ?, tags = ?, pinned = ?, archived = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_body,
                    json.dumps(next_tags, ensure_ascii=False),
                    int(next_pinned),
                    int(next_archived),
                    now_iso(),
                    note_id,
                ),
            )
            conn.commit()

        return self.get_note(note_id)

    def delete_note(self, note_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
        return cursor.rowcount > 0

    def export_notes(self) -> list[Note]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM notes ORDER BY id ASC").fetchall()
        return [self._row_to_note(row) for row in rows]

    def _insert_note_with_id(self, note: Note) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, title, body, tags, pinned, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.title,
                    note.body,
                    json.dumps(normalize_tags(note.tags), ensure_ascii=False),
                    int(note.pinned),
                    int(note.archived),
                    note.created_at,
                    note.updated_at,
                ),
            )
            conn.commit()

    def _overwrite_note(self, note: Note) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, body = ?, tags = ?, pinned = ?, archived = ?,
                    created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    note.title,
                    note.body,
                    json.dumps(normalize_tags(note.tags), ensure_ascii=False),
                    int(note.pinned),
                    int(note.archived),
                    note.created_at,
                    note.updated_at,
                    note.id,
                ),
            )
            conn.commit()

    def import_notes(self, notes: list[dict], *, mode: ImportMode) -> tuple[int, int, int]:
        inserted = 0
        updated = 0
        skipped = 0

        for idx, item in enumerate(notes, start=1):
            note = _parse_import_item(item, index=idx)
            existing = self.get_note(note.id)
            if existing is None:
                self._insert_note_with_id(note)
                inserted += 1
                continue

            if mode == "skip":
                skipped += 1
                continue

            self._overwrite_note(note)
            updated += 1

        return inserted, updated, skipped


class JSONBackend:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path

    def initialize(self) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        if self.json_path.exists():
            return
        self._save({"next_id": 1, "notes": []})

    def is_initialized(self) -> bool:
        return self.json_path.exists()

    def _load(self) -> dict:
        if not self.json_path.exists():
            return {"next_id": 1, "notes": []}

        payload = json.loads(self.json_path.read_text(encoding="utf-8"))
        payload.setdefault("next_id", 1)
        payload.setdefault("notes", [])
        return payload

    def _save(self, payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        self.json_path.write_text(serialized, encoding="utf-8")

    def _to_notes(self, payload: dict) -> list[Note]:
        return [Note.from_dict(item) for item in payload.get("notes", [])]

    def add_note(self, *, title: str | None, body: str, tags: list[str], pinned: bool) -> Note:
        body_clean = body.strip()
        if not body_clean:
            raise ValueError("Body must not be empty.")

        payload = self._load()
        note_id = int(payload["next_id"])
        payload["next_id"] = note_id + 1

        note = Note(
            id=note_id,
            title=title.strip() if isinstance(title, str) and title.strip() else None,
            body=body_clean,
            tags=normalize_tags(tags),
            pinned=bool(pinned),
            archived=False,
        )
        payload["notes"].append(note.to_dict())
        self._save(payload)
        return note

    def get_note(self, note_id: int) -> Note | None:
        payload = self._load()
        for item in payload["notes"]:
            if int(item.get("id", -1)) == note_id:
                return Note.from_dict(item)
        return None

    def list_notes(
        self,
        *,
        limit: int,
        tags: list[str],
        pinned_only: bool,
        archived_mode: ListMode,
    ) -> list[Note]:
        notes = self._to_notes(self._load())

        if pinned_only:
            notes = [note for note in notes if note.pinned]

        if archived_mode == "active":
            notes = [note for note in notes if not note.archived]
        elif archived_mode == "archived":
            notes = [note for note in notes if note.archived]

        notes = [note for note in notes if _match_tags(note.tags, tags)]
        notes.sort(key=lambda note: (note.updated_at, note.id), reverse=True)
        return notes[: max(limit, 0)]

    def search_notes(self, *, query: str, tags: list[str]) -> list[Note]:
        needle = query.casefold()
        notes = self._to_notes(self._load())
        filtered: list[Note] = []
        for note in notes:
            if note.archived:
                continue
            title = (note.title or "").casefold()
            body = note.body.casefold()
            if needle in title or needle in body:
                filtered.append(note)

        filtered = [note for note in filtered if _match_tags(note.tags, tags)]
        filtered.sort(key=lambda note: (note.updated_at, note.id), reverse=True)
        return filtered

    def update_note(
        self,
        note_id: int,
        *,
        title: str | None | object = MISSING,
        body: str | object = MISSING,
        tags: list[str] | object = MISSING,
        pinned: bool | object = MISSING,
        archived: bool | object = MISSING,
    ) -> Note | None:
        payload = self._load()
        for idx, item in enumerate(payload["notes"]):
            if int(item.get("id", -1)) != note_id:
                continue

            note = Note.from_dict(item)

            if title is not MISSING:
                if isinstance(title, str):
                    clean = title.strip()
                    note.title = clean if clean else None
                else:
                    note.title = None

            if body is not MISSING:
                clean_body = str(body).strip()
                if not clean_body:
                    raise ValueError("Body must not be empty.")
                note.body = clean_body

            if tags is not MISSING:
                note.tags = normalize_tags(tags if isinstance(tags, list) else [])

            if pinned is not MISSING:
                note.pinned = bool(pinned)

            if archived is not MISSING:
                note.archived = bool(archived)

            note.updated_at = now_iso()
            payload["notes"][idx] = note.to_dict()
            self._save(payload)
            return note

        return None

    def delete_note(self, note_id: int) -> bool:
        payload = self._load()
        original_len = len(payload["notes"])
        payload["notes"] = [item for item in payload["notes"] if int(item.get("id", -1)) != note_id]
        deleted = len(payload["notes"]) != original_len
        if deleted:
            self._save(payload)
        return deleted

    def export_notes(self) -> list[Note]:
        notes = self._to_notes(self._load())
        notes.sort(key=lambda note: note.id)
        return notes

    def import_notes(self, notes: list[dict], *, mode: ImportMode) -> tuple[int, int, int]:
        payload = self._load()
        existing_by_id = {int(item["id"]): item for item in payload["notes"]}

        inserted = 0
        updated = 0
        skipped = 0

        for idx, item in enumerate(notes, start=1):
            note = _parse_import_item(item, index=idx)
            if note.id in existing_by_id:
                if mode == "skip":
                    skipped += 1
                    continue
                existing_by_id[note.id] = note.to_dict()
                updated += 1
                continue

            existing_by_id[note.id] = note.to_dict()
            inserted += 1

        merged = list(existing_by_id.values())
        merged.sort(key=lambda row: int(row["id"]))
        payload["notes"] = merged
        max_id = max((int(item["id"]) for item in merged), default=0)
        payload["next_id"] = max(max_id + 1, int(payload.get("next_id", 1)))
        self._save(payload)

        return inserted, updated, skipped
