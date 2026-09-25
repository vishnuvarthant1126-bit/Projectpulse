"""Keyword, semantic and hybrid (reciprocal rank fusion) retrieval, scoped to one project.

Pipeline for a question:
1. Rank candidates with BM25 and/or Chroma (top `retrieval_candidates` each).
2. Hybrid: fuse the two ranked lists with RRF: score(d) = sum 1 / (rrf_k + rank_i(d)).
3. Deduplicate (chunk id, then identical normalised text).
4. Coverage rules: change/comparison questions must see the original plan *and* updates;
   status/blocker questions must see the latest progress update.
5. Return at most `answer_max_passages` passages for the answer model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Settings
from .db import Database
from .embeddings import Embedder
from .keyword import KeywordIndex
from .models import Passage, RetrievalMode
from .vectorstore import VectorStore

_CHANGE = re.compile(
    r"\b(chang\w*|delay\w*|slip\w*|late|later|behind|mov(e|ed)|re-?plan\w*|re-?baselin\w*|original\w*|"
    r"compar\w*|versus|vs\.?|differ\w*|on track|schedule\w*|deadline\w*|milestone\w*|target\w*|baseline)\b",
    re.I,
)
_STATUS = re.compile(
    r"\b(block\w*|unresolved|resolv\w*|open|outstanding|remain\w*|still|latest|current\w*|now|attention|"
    r"risk\w*|pending|status|need\w*)\b",
    re.I,
)


def detect_intents(question: str) -> list[str]:
    intents = []
    if _CHANGE.search(question):
        intents.append("change")
    if _STATUS.search(question):
        intents.append("status")
    return intents


def rrf_fuse(rankings: list[list[str]], k: int) -> list[tuple[str, float]]:
    """Reciprocal rank fusion over ranked id lists (rank starts at 1)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], t[0]))


@dataclass
class Candidate:
    chunk_id: str
    fused_rank: int | None = None
    rrf_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    semantic_rank: int | None = None
    semantic_score: float | None = None
    included_for: str | None = None


@dataclass
class RetrievalResult:
    mode: RetrievalMode
    intents: list[str]
    ranked: list[Candidate]  # full ranked list (before coverage rules / truncation)
    passages: list[Passage] = field(default_factory=list)  # final evidence set


class Retriever:
    def __init__(
        self, settings: Settings, db: Database, embedder: Embedder, vectors: VectorStore, keyword: KeywordIndex
    ):
        self.s = settings
        self.db = db
        self.embedder = embedder
        self.vectors = vectors
        self.keyword = keyword
        self._qcache: dict[str, list[float]] = {}

    def _embed_query(self, query: str) -> list[float]:
        # One question triggers several ranked searches (main + coverage groups); embed it once.
        cache = self._qcache
        if query not in cache:
            if len(cache) > 256:
                cache.clear()
            cache[query] = self.embedder.embed([query])[0]
        return cache[query]

    # -- loaders ---------------------------------------------------------------

    def _bm25_rows(self, project_id: str) -> list[tuple[str, str, str]]:
        rows = self.db.query(
            """SELECT c.id, c.index_text, d.doc_type, c.document_id FROM chunks c JOIN documents d ON d.id = c.document_id
               WHERE c.project_id = ? AND d.project_id = ? AND d.status = 'ready' ORDER BY c.id""",
            (project_id, project_id),
        )
        return [(r["id"], r["index_text"], r["doc_type"], r["document_id"]) for r in rows]

    def _load_chunks(self, project_id: str, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        rows = self.db.query(
            f"""SELECT c.*, d.filename AS document_name, d.doc_type, d.reporting_date
                FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE c.id IN ({marks}) AND c.project_id = ? AND d.project_id = ? AND d.status = 'ready'""",
            (*ids, project_id, project_id),
        )
        return {r["id"]: r for r in rows}

    def _doc_ids_of_type(self, project_id: str, doc_types: set[str]) -> list[dict]:
        marks = ",".join("?" * len(doc_types))
        return self.db.query(
            f"""SELECT id, doc_type, reporting_date FROM documents
                WHERE project_id = ? AND status = 'ready' AND doc_type IN ({marks})""",
            (project_id, *sorted(doc_types)),
        )

    # -- ranking ---------------------------------------------------------------

    def rank(
        self,
        project_id: str,
        query: str,
        mode: RetrievalMode,
        doc_types: set[str] | None = None,
        document_ids: set[str] | None = None,
        n: int | None = None,
    ) -> list[Candidate]:
        n = n or self.s.retrieval_candidates
        kw: list[tuple[str, float]] = []
        sem: list[tuple[str, float]] = []
        if mode in ("keyword", "hybrid"):
            kw = self.keyword.search(project_id, query, n, self._bm25_rows, doc_types, document_ids)
        if mode in ("semantic", "hybrid"):
            where = None
            if document_ids:
                where = {"document_id": {"$in": sorted(document_ids)}}
            elif doc_types:
                where = {"doc_type": {"$in": sorted(doc_types)}}
            qvec = self._embed_query(query)
            sem = self.vectors.query(project_id, qvec, n, where)

        # Guard: keep only chunks that exist, are ready, and belong to this project.
        valid = self._load_chunks(project_id, list({cid for cid, _ in kw} | {cid for cid, _ in sem}))
        if document_ids:
            valid = {k: v for k, v in valid.items() if v["document_id"] in document_ids}
        kw = [(c, s) for c, s in kw if c in valid][:n]
        sem = [(c, s) for c, s in sem if c in valid][:n]

        cands: dict[str, Candidate] = {}
        for r, (cid, score) in enumerate(kw, start=1):
            c = cands.setdefault(cid, Candidate(cid))
            c.keyword_rank, c.keyword_score = r, round(score, 4)
        for r, (cid, score) in enumerate(sem, start=1):
            c = cands.setdefault(cid, Candidate(cid))
            c.semantic_rank, c.semantic_score = r, round(score, 4)

        if mode == "keyword":
            order = [(c, None) for c, _ in kw]
        elif mode == "semantic":
            order = [(c, None) for c, _ in sem]
        else:
            order = rrf_fuse([[c for c, _ in kw], [c for c, _ in sem]], self.s.rrf_k)
            # Exact RRF ties (e.g. rank 1 in one list only vs rank 1 in the other only) are broken
            # deterministically by document name and position, so results are reproducible.
            order.sort(key=lambda t: (-t[1], valid[t[0]]["document_name"], valid[t[0]]["ordinal"]))

        ranked: list[Candidate] = []
        seen_text: set[str] = set()
        for cid, score in order:
            norm = re.sub(r"\s+", " ", valid[cid]["text"].lower()).strip()
            if norm in seen_text:
                continue  # identical passage text already ranked higher
            seen_text.add(norm)
            c = cands[cid]
            c.rrf_score = round(score, 5) if score is not None else None
            c.fused_rank = len(ranked) + 1
            ranked.append(c)
        return ranked

    # -- evidence selection ----------------------------------------------------

    def retrieve(
        self, project_id: str, question: str, mode: RetrievalMode, max_passages: int | None = None
    ) -> RetrievalResult:
        max_passages = max_passages or self.s.answer_max_passages
        intents = detect_intents(question)
        ranked = self.rank(project_id, question, mode)
        by_id = {c.chunk_id: c for c in ranked}

        groups: list[tuple[str, int, list[Candidate]]] = []
        if "change" in intents:
            groups.append(
                ("original plan", self.s.plan_quota, self._group(project_id, question, mode, ranked, {"original_plan"}))
            )
            groups.append(
                (
                    "progress updates",
                    self.s.update_quota,
                    self._group(project_id, question, mode, ranked, {"progress_update", "meeting_notes"}),
                )
            )
        if "status" in intents:
            latest = self._latest_update(project_id)
            if latest:
                groups.append(
                    ("latest progress update", 2, self._group(project_id, question, mode, ranked, None, {latest}))
                )

        selected: list[Candidate] = []
        chosen: set[str] = set()
        for label, quota, members in groups:
            have = sum(1 for c in selected if c.chunk_id in {m.chunk_id for m in members})
            for m in members:
                if have >= quota or len(selected) >= max_passages:
                    break
                if m.chunk_id in chosen:
                    continue
                cand = by_id.get(m.chunk_id, m)
                if cand.fused_rank is None or cand.fused_rank > max_passages:
                    cand.included_for = f"coverage: {label}"
                selected.append(cand)
                chosen.add(m.chunk_id)
                have += 1
        for c in ranked:
            if len(selected) >= max_passages:
                break
            if c.chunk_id not in chosen:
                selected.append(c)
                chosen.add(c.chunk_id)

        selected.sort(key=lambda c: (c.fused_rank is None, c.fused_rank or 0))
        return RetrievalResult(mode, intents, ranked, self.to_passages(project_id, selected))

    def _group(
        self,
        project_id: str,
        question: str,
        mode: RetrievalMode,
        ranked: list[Candidate],
        doc_types: set[str] | None,
        document_ids: set[str] | None = None,
    ) -> list[Candidate]:
        """Best passages from a subset of documents, in main-ranking order first."""
        if doc_types:
            docs = self._doc_ids_of_type(project_id, doc_types)
            document_ids = {d["id"] for d in docs}
        if not document_ids:
            return []
        rows = self._load_chunks(project_id, [c.chunk_id for c in ranked])
        in_main = [c for c in ranked if rows.get(c.chunk_id, {}).get("document_id") in document_ids]
        extra = self.rank(project_id, question, mode, document_ids=document_ids, n=5)
        seen = {c.chunk_id for c in in_main}
        for c in extra:
            if c.chunk_id not in seen:
                in_main.append(Candidate(c.chunk_id, keyword_score=c.keyword_score, semantic_score=c.semantic_score))
                seen.add(c.chunk_id)
        return in_main

    def _latest_update(self, project_id: str) -> str | None:
        row = self.db.one(
            """SELECT id FROM documents WHERE project_id = ? AND status = 'ready' AND doc_type = 'progress_update'
               AND reporting_date IS NOT NULL ORDER BY reporting_date DESC, created_at DESC LIMIT 1""",
            (project_id,),
        )
        return row["id"] if row else None

    def to_passages(self, project_id: str, cands: list[Candidate]) -> list[Passage]:
        rows = self._load_chunks(project_id, [c.chunk_id for c in cands])
        out: list[Passage] = []
        for c in cands:
            r = rows.get(c.chunk_id)
            if not r:
                continue
            out.append(
                Passage(
                    chunk_id=c.chunk_id,
                    document_id=r["document_id"],
                    document_name=r["document_name"],
                    doc_type=r["doc_type"],
                    reporting_date=r["reporting_date"],
                    heading=r["heading"],
                    page=r["page"],
                    section_id=r["section_id"],
                    char_start=r["char_start"],
                    char_end=r["char_end"],
                    text=r["text"],
                    rank=len(out) + 1,
                    fused_rank=c.fused_rank,
                    keyword_rank=c.keyword_rank,
                    semantic_rank=c.semantic_rank,
                    keyword_score=c.keyword_score,
                    semantic_score=c.semantic_score,
                    rrf_score=c.rrf_score,
                    included_for=c.included_for,
                )
            )
        return out
