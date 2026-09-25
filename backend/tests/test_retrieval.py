"""Retrieval behaviour: tokenisation, RRF, modes, coverage rules, dedupe, readiness."""

import pytest

from app.chunking import split_text
from app.demo import ensure_sample_project
from app.keyword import tokenize
from app.retrieval import detect_intents, rrf_fuse

from .conftest import make_project, upload


def test_rrf_fusion_math_and_order():
    fused = rrf_fuse([["a", "b", "c"], ["c", "a", "d"]], k=60)
    scores = dict(fused)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert scores["d"] == pytest.approx(1 / 63)
    assert [cid for cid, _ in fused][:2] == ["a", "c"]  # in both lists, highest combined


def test_tokenizer_keeps_identifiers_and_parts():
    toks = tokenize("Ticket BCN-201 blocks M4; see SP-7781.")
    assert "bcn-201" in toks and "bcn" in toks and "201" in toks
    assert "m4" in toks and "sp-7781" in toks
    assert "the" not in tokenize("the blocker")


def test_intent_detection():
    assert "change" in detect_intents("Which milestones are delayed?")
    assert "status" in detect_intents("What blockers remain unresolved?")
    assert detect_intents("Who is Dana Okafor?") == []


def test_chunking_overlap_and_offsets():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    spans = split_text(text, chunk_size=300, overlap=60)
    assert len(spans) > 5
    for s in spans:
        assert text[s.start : s.end] == s.text
        assert len(s.text) <= 300
    # consecutive chunks overlap
    assert all(spans[i + 1].start < spans[i].end for i in range(len(spans) - 1))
    assert spans[-1].end == len(text)


@pytest.fixture
def sample(services):
    return ensure_sample_project(services)


def test_exact_identifier_ranks_first_in_keyword_mode(services, sample):
    ranked = services.retriever.rank(sample["id"], "BCN-201", "keyword")
    top = services.retriever.to_passages(sample["id"], ranked[:1])[0]
    assert "BCN-201" in top.text


def test_modes_populate_expected_rank_fields(services, sample):
    q = "ScanPoint API credentials"
    kw = services.retriever.rank(sample["id"], q, "keyword")
    sem = services.retriever.rank(sample["id"], q, "semantic")
    hyb = services.retriever.rank(sample["id"], q, "hybrid")
    assert kw and all(c.keyword_rank and c.semantic_rank is None for c in kw)
    assert sem and all(c.semantic_rank and c.keyword_rank is None for c in sem)
    assert hyb and all(c.rrf_score for c in hyb)
    assert [c.fused_rank for c in hyb] == list(range(1, len(hyb) + 1))
    assert len({c.chunk_id for c in hyb}) == len(hyb)  # deduplicated


def test_change_questions_include_plan_and_updates(services, sample):
    res = services.retriever.retrieve(sample["id"], "How has the go-live schedule changed?", "keyword")
    types = [p.doc_type for p in res.passages]
    assert "original_plan" in types
    assert any(t in ("progress_update", "meeting_notes") for t in types)
    assert len(res.passages) <= services.settings.answer_max_passages


def test_status_questions_include_latest_update(services, sample):
    latest = services.db.one(
        "SELECT id FROM documents WHERE project_id = ? AND doc_type = 'progress_update' ORDER BY reporting_date DESC LIMIT 1",
        (sample["id"],),
    )["id"]
    for mode in ("keyword", "semantic", "hybrid"):
        res = services.retriever.retrieve(sample["id"], "What blockers remain unresolved?", mode)
        assert any(p.document_id == latest for p in res.passages), mode


def test_passages_preserve_metadata(services, sample):
    res = services.retriever.retrieve(sample["id"], "milestone target dates in the plan", "hybrid")
    plan = [p for p in res.passages if p.doc_type == "original_plan"]
    assert plan and all(p.page in (1, 2, 3) and p.reporting_date == "2026-01-12" for p in plan)
    assert all(p.document_name and p.section_id for p in res.passages)


def test_identical_text_is_deduplicated(client, services):
    pid = make_project(client)
    upload(client, pid, "a.md", "# A\n\nThe orbital relay is delayed.\n\nExtra line one.", reporting_date="2026-01-01")
    upload(client, pid, "b.md", "# B\n\nThe orbital relay is delayed.\n\nExtra line two.", reporting_date="2026-01-02")
    # Both documents contain a chunk whose text differs only by heading; add an exact duplicate chunk:
    upload(client, pid, "c.txt", "The orbital relay is delayed.\n\nExtra line one.", reporting_date="2026-01-03")
    ranked = services.retriever.rank(pid, "orbital relay delayed", "keyword")
    texts = [services.retriever.to_passages(pid, [c])[0].text for c in ranked]
    assert len(texts) == len(set(t.lower() for t in texts))


def test_documents_awaiting_review_are_not_searchable(client, services):
    pid = make_project(client)
    doc = upload(
        client, pid, "r.md", "# Report\n\nWeek ending: 6 March 2026\n\nThe halcyon feed is live.", reporting_date=None
    ).json()
    assert client.get(f"/api/documents/{doc['id']}").json()["status"] == "needs_review"
    for mode in ("keyword", "semantic", "hybrid"):
        assert (
            client.post(f"/api/projects/{pid}/search", json={"query": "halcyon feed", "mode": mode}).json()["passages"]
            == []
        )
    client.patch(f"/api/documents/{doc['id']}", json={"reporting_date": "2026-03-06"})
    assert client.post(f"/api/projects/{pid}/search", json={"query": "halcyon feed", "mode": "keyword"}).json()[
        "passages"
    ]


def test_changing_doc_type_updates_filters(client, services):
    pid = make_project(client)
    doc = upload(client, pid, "p.md", "# Plan\n\nThe lumen milestone target is 3 April 2026.", doc_type="other").json()
    upload(client, pid, "u.md", "# Update\n\nThe lumen milestone moved to 10 April 2026.")
    res = services.retriever.retrieve(pid, "How did the lumen milestone change?", "hybrid")
    assert "original_plan" not in {p.doc_type for p in res.passages}
    client.patch(f"/api/documents/{doc['id']}", json={"doc_type": "original_plan"})
    res = services.retriever.retrieve(pid, "How did the lumen milestone change?", "semantic")
    assert "original_plan" in {p.doc_type for p in res.passages}
