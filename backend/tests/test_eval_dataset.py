"""Integrity of the evaluation dataset and correctness of the retrieval metrics."""

import json
import sys

import pytest

from app.config import REPO_ROOT
from app.demo import ensure_sample_project

sys.path.insert(0, str(REPO_ROOT / "eval"))
from run_retrieval_eval import recall_at, reciprocal_rank  # noqa: E402

QUESTIONS = json.loads((REPO_ROOT / "eval" / "questions.json").read_text())["questions"]


def test_dataset_shape():
    assert len(QUESTIONS) == 30
    assert len({q["id"] for q in QUESTIONS}) == 30
    cats = {q["category"] for q in QUESTIONS}
    assert cats == {"exact", "paraphrase", "comparison", "conflict", "unanswerable"}
    for q in QUESTIONS:
        assert q["reference_answer"].strip()
        if q["answerable"]:
            assert q["supporting"], q["id"]


def test_every_supporting_quote_exists_in_exactly_the_named_document(services):
    import re

    project = ensure_sample_project(services)

    def norm(s):
        return re.sub(r"\s+", " ", s).strip().lower()

    for q in QUESTIONS:
        for sup in q["supporting"]:
            rows = services.db.query(
                "SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.project_id = ? AND d.filename = ?",
                (project["id"], sup["doc"]),
            )
            assert any(norm(sup["quote"]) in norm(r["text"]) for r in rows), (q["id"], sup["quote"])


def test_metric_math():
    quotes = [{"a"}, {"x", "y"}]
    ranked = ["b", "y", "a", "c"]
    assert recall_at(ranked, quotes, 1) == 0.0
    assert recall_at(ranked, quotes, 2) == pytest.approx(0.5)
    assert recall_at(ranked, quotes, 3) == pytest.approx(1.0)
    assert reciprocal_rank(ranked, quotes) == pytest.approx(0.5)
    assert reciprocal_rank(["z"], quotes) == 0.0
