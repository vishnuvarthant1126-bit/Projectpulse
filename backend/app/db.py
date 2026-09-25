"""SQLite storage for projects, document metadata, processing status, sections and chunks.

Vectors live in Chroma; everything else (including chunk text for BM25 and the
source viewer) lives here so it can be deleted atomically per document.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_sample INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    title TEXT,                       -- first heading, used as retrieval context
    file_ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    reporting_date TEXT,              -- ISO date confirmed by the user
    detected_date TEXT,               -- ISO date suggested from the content, never auto-applied
    detected_date_source TEXT,        -- short snippet the date was detected from
    status TEXT NOT NULL,             -- uploaded|extracting|needs_review|indexing|ready|failed
    error TEXT,
    page_count INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, sha256)
);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);

CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT,
    page INTEGER,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sections_document ON sections(document_id);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    section_id TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT,
    page INTEGER,
    char_start INTEGER NOT NULL,      -- offsets within the section text
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    index_text TEXT NOT NULL          -- title + heading + text, used by BM25 and embeddings
);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple | dict = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
