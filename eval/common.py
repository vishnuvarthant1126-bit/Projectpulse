"""Shared helpers for the evaluation scripts: build an isolated index of the sample
project, load questions, and map supporting quotes to relevant chunk IDs."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.demo import ensure_sample_project  # noqa: E402
from app.services import Services, build_services  # noqa: E402

QUESTIONS_PATH = ROOT / "eval" / "questions.json"
RESULTS_DIR = ROOT / "eval" / "results"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS_PATH.read_text())["questions"]


def build_eval_services(**overrides) -> tuple[Services, dict]:
    """Index the sample project into a throwaway data directory.

    Settings come from the environment/.env like the app (so EMBEDDING_* and LLM_* apply),
    with the data directory replaced so evaluation never touches real user data."""
    tmp = Path(tempfile.mkdtemp(prefix="projectpulse-eval-"))
    settings = Settings(data_dir=tmp, **overrides)
    svc = build_services(settings)
    project = ensure_sample_project(svc)
    return svc, project


def relevant_chunks(svc: Services, project_id: str, question: dict) -> list[set[str]]:
    """For each supporting quote, the set of chunk IDs whose text contains it.

    Raises if a quote cannot be found, so a typo in the dataset fails loudly instead of
    silently lowering recall."""
    out: list[set[str]] = []
    for sup in question["supporting"]:
        rows = svc.db.query(
            """SELECT c.id, c.text FROM chunks c JOIN documents d ON d.id = c.document_id
               WHERE c.project_id = ? AND d.filename = ?""",
            (project_id, sup["doc"]),
        )
        q = norm(sup["quote"])
        ids = {r["id"] for r in rows if q in norm(r["text"])}
        if not ids:
            raise ValueError(f"{question['id']}: supporting quote not found in {sup['doc']}: {sup['quote'][:60]}")
        out.append(ids)
    return out
