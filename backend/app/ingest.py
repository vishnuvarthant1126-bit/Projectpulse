"""Document lifecycle: validate -> store -> extract -> chunk -> (user confirms date) -> index.

Status flow:  uploaded -> extracting -> needs_review -> indexing -> ready
                                   \\-> failed (with a user-facing error)
A document is searchable only when `ready`. If a reporting date is supplied at upload
time the review step is skipped; otherwise the user must confirm the detected date.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .chunking import index_text, split_text
from .dates import detect_reporting_date
from .extraction import ExtractionError, extract
from .services import Services

log = logging.getLogger("projectpulse.ingest")


class UploadError(Exception):
    def __init__(self, message: str, status_code: int = 400, existing: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.existing = existing


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def safe_filename(name: str) -> str:
    name = Path(name or "document").name
    name = re.sub(r"[\x00-\x1f\x7f/\\]", "", name).strip() or "document"
    return name[:200]


def validate_upload(svc: Services, filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in svc.settings.allowed_extensions:
        raise UploadError(
            f"Unsupported file type '{ext or 'none'}'. Upload a PDF, Markdown (.md) or text (.txt) file.", 415
        )
    max_bytes = int(svc.settings.max_upload_mb * 1024 * 1024)
    if len(data) == 0:
        raise UploadError("The file is empty.")
    if len(data) > max_bytes:
        raise UploadError(f"The file is larger than the {svc.settings.max_upload_mb:g} MB upload limit.", 413)
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise UploadError("This file has a .pdf extension but is not a PDF.", 415)
    if ext != ".pdf" and b"\x00" in data[:8192]:
        raise UploadError("This file looks binary, not text. Upload a PDF, Markdown or text file.", 415)
    return ext


def create_document(
    svc: Services, project_id: str, filename: str, data: bytes, doc_type: str, reporting_date: str | None
) -> dict[str, Any]:
    filename = safe_filename(filename)
    ext = validate_upload(svc, filename, data)
    sha = hashlib.sha256(data).hexdigest()
    existing = svc.db.one(
        "SELECT id, filename, status FROM documents WHERE project_id = ? AND sha256 = ?", (project_id, sha)
    )
    if existing:
        raise UploadError(
            f"Duplicate upload: this file is identical to '{existing['filename']}' already in this project.",
            409,
            existing,
        )
    doc_id = uuid.uuid4().hex
    path = svc.settings.uploads_dir / project_id / f"{doc_id}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    ts = now()
    svc.db.execute(
        """INSERT INTO documents (id, project_id, filename, file_ext, size_bytes, sha256, doc_type, reporting_date,
           status, chunk_count, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, 'uploaded', 0, ?, ?)""",
        (doc_id, project_id, filename, ext, len(data), sha, doc_type, reporting_date, ts, ts),
    )
    log.info("document uploaded id=%s project=%s ext=%s bytes=%d", doc_id, project_id, ext, len(data))
    return get_document(svc, doc_id)


def get_document(svc: Services, doc_id: str) -> dict[str, Any] | None:
    return svc.db.one("SELECT * FROM documents WHERE id = ?", (doc_id,))


def _set_status(svc: Services, doc_id: str, status: str, error: str | None = None, **extra: Any) -> None:
    cols = ["status = ?", "error = ?", "updated_at = ?"]
    vals: list[Any] = [status, error, now()]
    for k, v in extra.items():
        cols.append(f"{k} = ?")
        vals.append(v)
    svc.db.execute(f"UPDATE documents SET {', '.join(cols)} WHERE id = ?", (*vals, doc_id))


def process_document(svc: Services, doc_id: str) -> None:
    """Extract and chunk. Runs in a background thread after upload."""
    doc = get_document(svc, doc_id)
    if not doc:
        return
    _set_status(svc, doc_id, "extracting")
    path = svc.settings.uploads_dir / doc["project_id"] / f"{doc_id}{doc['file_ext']}"
    try:
        extracted = extract(path.read_bytes(), doc["file_ext"], svc.settings.min_chars_per_pdf_page)
    except ExtractionError as exc:
        _set_status(svc, doc_id, "failed", str(exc))
        log.info("document extraction failed id=%s reason=%s", doc_id, type(exc).__name__)
        return
    except Exception:  # unexpected parser error: report generically, keep details in logs
        log.exception("document extraction crashed id=%s", doc_id)
        _set_status(
            svc, doc_id, "failed", "The document could not be read. It may be corrupted or in an unsupported format."
        )
        return

    title = next((s.heading for s in extracted.sections if s.heading), None) or Path(doc["filename"]).stem
    full_text = "\n\n".join((s.heading + "\n" if s.heading else "") + s.text for s in extracted.sections)
    detected, detected_src = detect_reporting_date(full_text, doc["filename"])

    s = svc.settings
    with svc.db.tx() as conn:
        conn.execute("DELETE FROM sections WHERE document_id = ?", (doc_id,))
        n_chunks = 0
        for si, sec in enumerate(extracted.sections):
            sec_id = f"{doc_id}-s{si}"
            conn.execute(
                "INSERT INTO sections (id, document_id, ordinal, heading, page, text) VALUES (?,?,?,?,?,?)",
                (sec_id, doc_id, si, sec.heading, sec.page, sec.text),
            )
            for span in split_text(sec.text, s.chunk_size, s.chunk_overlap):
                conn.execute(
                    """INSERT INTO chunks (id, document_id, project_id, section_id, ordinal, heading, page,
                       char_start, char_end, text, index_text) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        f"{doc_id}-c{n_chunks}",
                        doc_id,
                        doc["project_id"],
                        sec_id,
                        n_chunks,
                        sec.heading,
                        sec.page,
                        span.start,
                        span.end,
                        span.text,
                        index_text(title, sec.heading, span.text),
                    ),
                )
                n_chunks += 1
        conn.execute(
            """UPDATE documents SET title = ?, page_count = ?, chunk_count = ?, detected_date = ?,
               detected_date_source = ?, status = 'needs_review', error = NULL, updated_at = ? WHERE id = ?""",
            (title, extracted.page_count, n_chunks, detected, detected_src, now(), doc_id),
        )
    log.info("document extracted id=%s sections=%d chunks=%d", doc_id, len(extracted.sections), n_chunks)

    if doc["reporting_date"]:  # date supplied (and therefore confirmed) at upload time
        index_document(svc, doc_id)


def _vector_metadata(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": doc["project_id"],
        "document_id": doc["id"],
        "doc_type": doc["doc_type"],
        "reporting_date": doc["reporting_date"] or "",
    }


def index_document(svc: Services, doc_id: str) -> None:
    doc = get_document(svc, doc_id)
    if not doc or not doc["reporting_date"]:
        return
    _set_status(svc, doc_id, "indexing")
    chunks = svc.db.query("SELECT id, index_text FROM chunks WHERE document_id = ? ORDER BY ordinal", (doc_id,))
    try:
        vectors = svc.embedder.embed([c["index_text"] for c in chunks])
        svc.vectors.delete_document(doc["project_id"], doc_id)
        meta = _vector_metadata(doc)
        svc.vectors.add(doc["project_id"], [c["id"] for c in chunks], vectors, [meta] * len(chunks))
    except Exception as exc:
        log.exception("document indexing failed id=%s", doc_id)
        _set_status(
            svc, doc_id, "failed", f"Indexing failed: {type(exc).__name__}. Check the embedding settings and retry."
        )
        return
    _set_status(svc, doc_id, "ready")
    svc.keyword.invalidate(doc["project_id"])
    log.info("document indexed id=%s chunks=%d", doc_id, len(chunks))


def update_document(svc: Services, doc_id: str, doc_type: str | None, reporting_date: str | None) -> dict[str, Any]:
    doc = get_document(svc, doc_id)
    if not doc:
        raise UploadError("Document not found.", 404)
    if doc_type:
        svc.db.execute("UPDATE documents SET doc_type = ?, updated_at = ? WHERE id = ?", (doc_type, now(), doc_id))
    if reporting_date:
        svc.db.execute(
            "UPDATE documents SET reporting_date = ?, updated_at = ? WHERE id = ?", (reporting_date, now(), doc_id)
        )
    doc = get_document(svc, doc_id)
    if doc["status"] == "needs_review" and doc["reporting_date"]:
        index_document(svc, doc_id)
    elif doc["status"] == "ready":
        svc.vectors.update_metadata(doc["project_id"], doc_id, _vector_metadata(doc))
        svc.keyword.invalidate(doc["project_id"])
    return get_document(svc, doc_id)


def delete_document(svc: Services, doc_id: str) -> bool:
    doc = get_document(svc, doc_id)
    if not doc:
        return False
    svc.vectors.delete_document(doc["project_id"], doc_id)
    with svc.db.tx() as conn:
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM sections WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    path = svc.settings.uploads_dir / doc["project_id"] / f"{doc_id}{doc['file_ext']}"
    path.unlink(missing_ok=True)
    svc.keyword.invalidate(doc["project_id"])
    log.info("document deleted id=%s project=%s", doc_id, doc["project_id"])
    return True


def create_project(svc: Services, name: str, description: str = "", is_sample: bool = False) -> dict[str, Any]:
    pid = uuid.uuid4().hex
    svc.db.execute(
        "INSERT INTO projects (id, name, description, is_sample, created_at) VALUES (?,?,?,?,?)",
        (pid, name.strip(), description.strip(), int(is_sample), now()),
    )
    return svc.db.one("SELECT * FROM projects WHERE id = ?", (pid,))


def delete_project(svc: Services, project_id: str) -> bool:
    if not svc.db.one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        return False
    for d in svc.db.query("SELECT id FROM documents WHERE project_id = ?", (project_id,)):
        delete_document(svc, d["id"])
    svc.vectors.delete_project(project_id)
    svc.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    svc.keyword.invalidate(project_id)
    return True
