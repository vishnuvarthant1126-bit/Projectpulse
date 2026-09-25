"""Pydantic models for the HTTP API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["original_plan", "progress_update", "meeting_notes", "other"]
DocStatus = Literal["uploaded", "extracting", "needs_review", "indexing", "ready", "failed"]
RetrievalMode = Literal["hybrid", "keyword", "semantic"]

DOC_TYPE_LABELS: dict[str, str] = {
    "original_plan": "Original plan",
    "progress_update": "Progress update",
    "meeting_notes": "Meeting notes",
    "other": "Other",
}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class Project(BaseModel):
    id: str
    name: str
    description: str
    is_sample: bool
    created_at: str
    document_count: int = 0


class Document(BaseModel):
    id: str
    project_id: str
    filename: str
    title: str | None
    doc_type: DocType
    reporting_date: str | None
    detected_date: str | None
    detected_date_source: str | None
    status: DocStatus
    error: str | None
    page_count: int | None
    chunk_count: int
    size_bytes: int
    created_at: str
    updated_at: str


class DocumentUpdate(BaseModel):
    doc_type: DocType | None = None
    reporting_date: date | None = None


class SectionOut(BaseModel):
    id: str
    ordinal: int
    heading: str | None
    page: int | None
    text: str


class ChunkRef(BaseModel):
    id: str
    section_id: str
    char_start: int
    char_end: int
    page: int | None


class DocumentContent(BaseModel):
    document: Document
    sections: list[SectionOut]
    chunks: list[ChunkRef]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    mode: RetrievalMode = "hybrid"
    k: int = Field(default=10, ge=1, le=50)


class Passage(BaseModel):
    source_id: str | None = None  # S1..Sn, assigned per answer by the backend
    chunk_id: str
    document_id: str
    document_name: str
    doc_type: DocType
    reporting_date: str | None
    heading: str | None
    page: int | None
    section_id: str
    char_start: int
    char_end: int
    text: str
    rank: int  # 1-based position in the final list
    fused_rank: int | None
    keyword_rank: int | None
    semantic_rank: int | None
    keyword_score: float | None
    semantic_score: float | None
    rrf_score: float | None
    included_for: str | None = None  # why a coverage rule added it


class SearchResponse(BaseModel):
    mode: RetrievalMode
    intents: list[str]
    passages: list[Passage]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: RetrievalMode = "hybrid"


# ---- Structured answer ------------------------------------------------------


class Finding(BaseModel):
    statement: str
    citations: list[str]


class ComparisonRow(BaseModel):
    milestone: str
    original_commitment: str
    latest_status: str
    reason_for_change: str
    owner: str
    citations: list[str]


class ConflictPosition(BaseModel):
    claim: str
    source_date: str
    citations: list[str]


class Conflict(BaseModel):
    topic: str
    positions: list[ConflictPosition]


class Blocker(BaseModel):
    blocker: str
    status: Literal["unresolved_in_latest", "resolved", "status_unknown"]
    detail: str
    citations: list[str]


class SuggestedAction(BaseModel):
    action: str
    rationale: str
    citations: list[str]


class Answer(BaseModel):
    answer_type: Literal["answer", "insufficient_evidence"]
    summary: str
    findings: list[Finding] = []
    comparison: list[ComparisonRow] = []
    conflicts: list[Conflict] = []
    blockers: list[Blocker] = []
    suggested_actions: list[SuggestedAction] = []
    missing_information: list[str] = []


class Validation(BaseModel):
    invalid_citations: list[str] = []  # IDs the model returned that were not retrieved
    removed_items: list[str] = []  # statements dropped because no valid citation remained
    unverified_dates: list[str] = []  # dates in the answer not found in the cited passages
    passed: bool = True


AnswerMode = Literal["live", "precomputed_demo", "retrieval_only", "no_evidence"]


class AskResponse(BaseModel):
    question: str
    mode: RetrievalMode
    answer_mode: AnswerMode
    notice: str | None = None
    model: str | None = None
    answer: Answer | None
    passages: list[Passage]
    validation: Validation
    intents: list[str]
    latency_ms: int
