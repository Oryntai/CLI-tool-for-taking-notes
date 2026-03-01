from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Note:
    id: int
    body: str
    title: str | None = None
    tags: list[str] = field(default_factory=list)
    pinned: bool = False
    archived: bool = False
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "pinned": self.pinned,
            "archived": self.archived,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        tags_raw = data.get("tags", [])
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        elif isinstance(tags_raw, list | tuple | set):
            tags = [str(tag) for tag in tags_raw]
        else:
            tags = []

        title_raw = data.get("title")
        return cls(
            id=int(data["id"]),
            title=None if title_raw is None else str(title_raw),
            body=str(data.get("body", "")),
            tags=tags,
            pinned=bool(data.get("pinned", False)),
            archived=bool(data.get("archived", False)),
            created_at=str(data.get("created_at", now_iso())),
            updated_at=str(data.get("updated_at", now_iso())),
        )
