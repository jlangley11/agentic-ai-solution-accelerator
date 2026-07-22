"""SQLite-backed, gitignored evidence ledger for customer source documents."""
from __future__ import annotations

import hashlib
import pathlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..repository import RepositoryContext

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    format TEXT NOT NULL,
    total_chars INTEGER NOT NULL,
    disclosure_status TEXT NOT NULL DEFAULT 'local_only',
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    source_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    level INTEGER,
    text TEXT NOT NULL,
    page INTEGER,
    heading TEXT,
    text_sha256 TEXT NOT NULL,
    PRIMARY KEY (source_id, chunk_id),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requirements (
    id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    confidence REAL,
    decision_note TEXT,
    approved_by TEXT,
    approved_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirement_evidence (
    requirement_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    PRIMARY KEY (requirement_id, source_id, chunk_id),
    FOREIGN KEY (requirement_id) REFERENCES requirements(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id, chunk_id) REFERENCES chunks(source_id, chunk_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conflicts (
    id TEXT PRIMARY KEY,
    left_requirement_id TEXT NOT NULL,
    right_requirement_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolution TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (left_requirement_id) REFERENCES requirements(id),
    FOREIGN KEY (right_requirement_id) REFERENCES requirements(id)
);

CREATE TABLE IF NOT EXISTS requirement_links (
    requirement_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    target TEXT NOT NULL,
    PRIMARY KEY (requirement_id, link_type, target),
    FOREIGN KEY (requirement_id) REFERENCES requirements(id) ON DELETE CASCADE
);
"""


@dataclass(frozen=True)
class IntakeSource:
    id: str
    source_path: str
    sha256: str
    format: str
    total_chars: int
    disclosure_status: str
    added_at: str
    chunk_count: int = 0


@dataclass(frozen=True)
class RequirementRecord:
    id: str
    statement: str
    category: str
    status: str
    confidence: float | None
    decision_note: str | None
    approved_by: str | None
    approved_at: str | None
    updated_at: str


class EvidenceLedger:
    def __init__(self, context: RepositoryContext) -> None:
        self.context = context
        self.path = context.private_dir / "evidence.db"

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(_SCHEMA)
            connection.commit()

    def add_extraction(
        self,
        source_path: pathlib.Path,
        extraction: dict[str, Any],
    ) -> IntakeSource:
        self.initialize()
        content_hash = _sha256_file(source_path)
        source_id = f"src-{content_hash[:16]}"
        added_at = datetime.now(UTC).isoformat()
        source_format = str(extraction.get("format") or source_path.suffix.lstrip("."))
        total_chars = int(extraction.get("total_chars") or 0)
        chunks = extraction.get("chunks") or []

        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO sources (
                    id, source_path, sha256, format, total_chars,
                    disclosure_status, added_at
                ) VALUES (?, ?, ?, ?, ?, 'local_only', ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    source_path = excluded.source_path,
                    format = excluded.format,
                    total_chars = excluded.total_chars
                """,
                (
                    source_id,
                    str(source_path),
                    content_hash,
                    source_format,
                    total_chars,
                    added_at,
                ),
            )
            connection.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            current_heading: str | None = None
            for raw in chunks:
                if not isinstance(raw, dict):
                    continue
                text = str(raw.get("text") or "").strip()
                if not text:
                    continue
                chunk_type = str(raw.get("type") or "paragraph")
                if chunk_type == "heading":
                    current_heading = text
                connection.execute(
                    """
                    INSERT INTO chunks (
                        source_id, chunk_id, chunk_type, level, text, page,
                        heading, text_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        str(raw.get("chunk_id") or ""),
                        chunk_type,
                        raw.get("level"),
                        text,
                        raw.get("page"),
                        current_heading,
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    ),
                )
            connection.commit()
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> IntakeSource:
        if not self.path.exists():
            raise KeyError(f"Unknown evidence source: {source_id}")
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                """
                SELECT s.id, s.source_path, s.sha256, s.format, s.total_chars,
                       s.disclosure_status, s.added_at, COUNT(c.chunk_id)
                FROM sources s
                LEFT JOIN chunks c ON c.source_id = s.id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown evidence source: {source_id}")
        return IntakeSource(*row)

    def list_sources(self) -> list[IntakeSource]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.source_path, s.sha256, s.format, s.total_chars,
                       s.disclosure_status, s.added_at, COUNT(c.chunk_id)
                FROM sources s
                LEFT JOIN chunks c ON c.source_id = s.id
                GROUP BY s.id
                ORDER BY s.added_at, s.id
                """
            ).fetchall()
        return [IntakeSource(*row) for row in rows]

    def set_disclosure(self, source_id: str, status: str) -> IntakeSource:
        if status not in {"local_only", "approved_for_model", "rejected"}:
            raise ValueError(f"Unsupported disclosure status: {status}")
        self.initialize()
        with closing(sqlite3.connect(self.path)) as connection:
            cursor = connection.execute(
                "UPDATE sources SET disclosure_status = ? WHERE id = ?",
                (status, source_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown evidence source: {source_id}")
            connection.commit()
        return self.get_source(source_id)

    def chunks(
        self,
        source_id: str,
        *,
        include_text: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.path.exists():
            raise KeyError(f"Unknown evidence source: {source_id}")
        if limit < 1 or limit > 500:
            raise ValueError("Chunk review limit must be between 1 and 500.")
        if offset < 0:
            raise ValueError("Chunk review offset must not be negative.")
        source = self.get_source(source_id)
        if source.chunk_count and offset >= source.chunk_count:
            raise ValueError(
                f"Chunk review offset {offset} is beyond the "
                f"{source.chunk_count}-chunk source."
            )
        if include_text and source.disclosure_status != "approved_for_model":
            raise PermissionError(
                f"Source {source_id} is {source.disclosure_status}; approve it "
                "before returning source text to an agent-facing command."
            )
        fields = (
            "chunk_id, chunk_type, level, text, page, heading"
            if include_text
            else "chunk_id, chunk_type, level, page, heading, length(text)"
        )
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                f"SELECT {fields} FROM chunks WHERE source_id = ? "  # noqa: S608
                "ORDER BY chunk_id LIMIT ? OFFSET ?",
                (source_id, limit, offset),
            ).fetchall()
        if include_text:
            keys = ("chunk_id", "type", "level", "text", "page", "heading")
        else:
            keys = ("chunk_id", "type", "level", "page", "heading", "text_length")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def duplicate_groups(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT text_sha256, COUNT(*), GROUP_CONCAT(source_id || ':' || chunk_id)
                FROM chunks
                GROUP BY text_sha256
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC, text_sha256
                """
            ).fetchall()
        return [
            {
                "text_sha256": row[0],
                "count": row[1],
                "locations": str(row[2]).split(","),
            }
            for row in rows
        ]

    def add_requirement(
        self,
        statement: str,
        category: str,
        *,
        confidence: float | None = None,
        evidence: list[tuple[str, str]] | None = None,
    ) -> RequirementRecord:
        self.initialize()
        normalized = " ".join(statement.split())
        if not normalized:
            raise ValueError("Requirement statement must not be empty.")
        requirement_id = (
            "req-"
            + hashlib.sha256(
                f"{category.strip().lower()}|{normalized}".encode("utf-8")
            ).hexdigest()[:16]
        )
        updated_at = datetime.now(UTC).isoformat()
        for source_id, chunk_id in evidence or []:
            source = self.get_source(source_id)
            if source.disclosure_status != "approved_for_model":
                raise PermissionError(
                    f"Evidence source {source_id} is {source.disclosure_status}; "
                    "approve it before linking extracted evidence."
                )
            with closing(sqlite3.connect(self.path)) as connection:
                exists = connection.execute(
                    """
                    SELECT 1 FROM chunks
                    WHERE source_id = ? AND chunk_id = ?
                    """,
                    (source_id, chunk_id),
                ).fetchone()
            if exists is None:
                raise KeyError(f"Unknown evidence chunk: {source_id}:{chunk_id}")
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO requirements (
                    id, statement, category, status, confidence, updated_at
                ) VALUES (?, ?, ?, 'proposed', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    statement = excluded.statement,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
                """,
                (
                    requirement_id,
                    normalized,
                    category.strip().lower(),
                    confidence,
                    updated_at,
                ),
            )
            for source_id, chunk_id in evidence or []:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO requirement_evidence (
                        requirement_id, source_id, chunk_id
                    ) VALUES (?, ?, ?)
                    """,
                    (requirement_id, source_id, chunk_id),
                )
            connection.commit()
        return self.get_requirement(requirement_id)

    def get_requirement(self, requirement_id: str) -> RequirementRecord:
        if not self.path.exists():
            raise KeyError(f"Unknown requirement: {requirement_id}")
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                """
                SELECT id, statement, category, status, confidence,
                       decision_note, approved_by, approved_at, updated_at
                FROM requirements
                WHERE id = ?
                """,
                (requirement_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown requirement: {requirement_id}")
        return RequirementRecord(*row)

    def list_requirements(self) -> list[RequirementRecord]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT id, statement, category, status, confidence,
                       decision_note, approved_by, approved_at, updated_at
                FROM requirements
                ORDER BY category, id
                """
            ).fetchall()
        return [RequirementRecord(*row) for row in rows]

    def decide_requirement(
        self,
        requirement_id: str,
        status: str,
        *,
        approved_by: str | None = None,
        note: str | None = None,
    ) -> RequirementRecord:
        if status not in {"proposed", "approved", "rejected", "deferred"}:
            raise ValueError(f"Unsupported requirement status: {status}")
        now = datetime.now(UTC).isoformat()
        approval_time = now if status == "approved" else None
        with closing(sqlite3.connect(self.path)) as connection:
            cursor = connection.execute(
                """
                UPDATE requirements
                SET status = ?, decision_note = ?, approved_by = ?,
                    approved_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    note,
                    approved_by,
                    approval_time,
                    now,
                    requirement_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown requirement: {requirement_id}")
            connection.commit()
        return self.get_requirement(requirement_id)

    def add_requirement_link(
        self,
        requirement_id: str,
        link_type: str,
        target: str,
    ) -> None:
        allowed = {
            "implementation",
            "quality_eval",
            "redteam",
            "telemetry",
            "ux",
            "decision",
        }
        if link_type not in allowed:
            raise ValueError(f"Unsupported requirement link type: {link_type}")
        self.get_requirement(requirement_id)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO requirement_links (
                    requirement_id, link_type, target
                ) VALUES (?, ?, ?)
                """,
                (requirement_id, link_type, target),
            )
            connection.commit()

    def requirement_links(self, requirement_id: str) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT link_type, target
                FROM requirement_links
                WHERE requirement_id = ?
                ORDER BY link_type, target
                """,
                (requirement_id,),
            ).fetchall()
        return [{"type": row[0], "target": row[1]} for row in rows]

    def requirement_evidence(self, requirement_id: str) -> list[str]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT source_id, chunk_id
                FROM requirement_evidence
                WHERE requirement_id = ?
                ORDER BY source_id, chunk_id
                """,
                (requirement_id,),
            ).fetchall()
        return [f"{row[0]}:{row[1]}" for row in rows]

    def export_summary(self) -> dict[str, Any]:
        sources = self.list_sources()
        return {
            "database": str(self.path),
            "sources": [
                {
                    **source.__dict__,
                    "source_path": pathlib.Path(source.source_path).name,
                }
                for source in sources
            ],
            "duplicate_groups": self.duplicate_groups(),
            "approved_source_ids": [
                source.id
                for source in sources
                if source.disclosure_status == "approved_for_model"
            ],
            "requirements": [
                {
                    **requirement.__dict__,
                    "evidence": self.requirement_evidence(requirement.id),
                    "links": self.requirement_links(requirement.id),
                }
                for requirement in self.list_requirements()
            ],
        }


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
