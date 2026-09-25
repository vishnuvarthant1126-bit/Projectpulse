"""Sample project loader and precomputed demo answers.

Precomputed answers were written ahead of time for the fictional sample project so
visitors can explore without an API key. They are always returned with
answer_mode="precomputed_demo" and a visible notice; they are never presented as live
AI output. Their citations are stored as (document, exact quote) anchors that are
resolved to real chunk IDs at request time and then pass through the same citation
validator as live answers.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .answering import assign_source_ids, validate_answer
from .ingest import create_document, create_project, delete_project, process_document
from .models import Answer, Passage, Validation
from .retrieval import Candidate
from .services import Services

log = logging.getLogger("projectpulse.demo")

PRECOMPUTED_NOTICE = (
    "Precomputed demo answer. It was written in advance for this fictional sample project and is not a live AI "
    "response. Citations are resolved to the passages below and validated by the backend."
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def sample_dir(svc: Services) -> Path:
    return svc.settings.sample_data_dir / "beacon"


def load_manifest(svc: Services) -> dict[str, Any]:
    return json.loads((sample_dir(svc) / "manifest.json").read_text())


def ensure_sample_project(svc: Services, reset: bool = False) -> dict[str, Any]:
    manifest = load_manifest(svc)
    existing = svc.db.one("SELECT * FROM projects WHERE is_sample = 1 ORDER BY created_at DESC LIMIT 1")
    if existing and not reset:
        ready = svc.db.one(
            "SELECT COUNT(*) AS n FROM documents WHERE project_id = ? AND status = 'ready'", (existing["id"],)
        )["n"]
        if ready == len(manifest["documents"]):
            return existing
    if existing:
        delete_project(svc, existing["id"])
    project = create_project(svc, manifest["project"]["name"], manifest["project"]["description"], is_sample=True)
    for entry in manifest["documents"]:
        data = (sample_dir(svc) / entry["file"]).read_bytes()
        doc = create_document(svc, project["id"], entry["file"], data, entry["doc_type"], entry["reporting_date"])
        process_document(svc, doc["id"])
    log.info("sample project ready id=%s", project["id"])
    return project


@lru_cache(maxsize=4)
def _load_precomputed(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    return json.loads(p.read_text())["answers"] if p.exists() else []


def precomputed_entries(svc: Services) -> list[dict[str, Any]]:
    return _load_precomputed(str(sample_dir(svc) / "precomputed_answers.json"))


def find_precomputed(svc: Services, question: str) -> dict[str, Any] | None:
    q = _norm(question).rstrip("?")
    for entry in precomputed_entries(svc):
        if _norm(entry["question"]).rstrip("?") == q:
            return entry
    return None


def resolve_anchor(svc: Services, project_id: str, anchor: dict[str, str]) -> str:
    """Return the chunk id whose text contains the anchor quote in the named document."""
    rows = svc.db.query(
        """SELECT c.id, c.text FROM chunks c JOIN documents d ON d.id = c.document_id
           WHERE c.project_id = ? AND d.filename = ? AND d.status = 'ready' ORDER BY c.ordinal""",
        (project_id, anchor["doc"]),
    )
    quote = _norm(anchor["quote"])
    for r in rows:
        if quote in _norm(r["text"]):
            return r["id"]
    raise LookupError(f"Anchor not found in {anchor['doc']}: {anchor['quote'][:60]}")


def build_precomputed_answer(
    svc: Services, project_id: str, entry: dict[str, Any], retrieved: list[Passage]
) -> tuple[Answer, Validation, list[Passage]]:
    anchors: dict[str, dict[str, str]] = entry["anchors"]
    anchor_chunk = {key: resolve_anchor(svc, project_id, a) for key, a in anchors.items()}

    # Evidence = anchored passages first (in anchor order), then retrieved passages.
    order: list[str] = []
    for cid in anchor_chunk.values():
        if cid not in order:
            order.append(cid)
    by_chunk = {p.chunk_id: p for p in retrieved}
    extra = [Candidate(cid) for cid in order if cid not in by_chunk]
    anchored = svc.retriever.to_passages(project_id, extra)
    for p in anchored:
        p.included_for = "cited by precomputed answer"
    passages = [by_chunk.get(cid) for cid in order]
    passages = [p for p in passages if p] + anchored
    passages.sort(key=lambda p: order.index(p.chunk_id))
    passages += [p for p in retrieved if p.chunk_id not in anchor_chunk.values()][: max(0, 8 - len(passages))]
    for i, p in enumerate(passages, start=1):
        p.rank = i
    assign_source_ids(passages)
    sid_of = {p.chunk_id: p.source_id for p in passages}

    def to_ids(keys: list[str]) -> list[str]:
        return [sid_of[anchor_chunk[k]] for k in keys]

    raw = json.loads(json.dumps(entry["answer"]))  # deep copy

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: (to_ids(v) if k == "citations" else walk(v)) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    raw = walk(raw)
    # Inline markers in the summary are written as {anchor_key}.
    raw["summary"] = re.sub(r"\{(\w+)\}", lambda m: f"[{sid_of[anchor_chunk[m.group(1)]]}]", raw.get("summary", ""))
    answer, validation = validate_answer(raw, passages)
    return answer, validation, passages
