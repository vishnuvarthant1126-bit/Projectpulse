from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.embeddings import HashEmbedder
from app.main import create_app
from app.services import build_services


class FakeLLM:
    """Returns a canned JSON answer and records the prompts it received."""

    name = "fake-llm"

    def __init__(self, payload: dict[str, Any] | None = None):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        self.calls.append((system, user))
        return json.dumps(self.payload or {})


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        sample_data_dir=REPO_ROOT / "sample_data",
        embedding_provider="hash",
        llm_provider="none",
        max_upload_mb=1,
        _env_file=None,
    )


@pytest.fixture
def services(settings):
    svc = build_services(settings, embedder=HashEmbedder())
    yield svc
    svc.db.close()


@pytest.fixture
def client(services):
    with TestClient(create_app(services)) as c:
        yield c


def make_project(client: TestClient, name: str = "Test project") -> str:
    r = client.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(
    client: TestClient,
    project_id: str,
    filename: str,
    content: bytes | str,
    doc_type: str = "progress_update",
    reporting_date: str | None = "2026-03-06",
):
    data = content.encode() if isinstance(content, str) else content
    form = {"doc_type": doc_type}
    if reporting_date:
        form["reporting_date"] = reporting_date
    return client.post(f"/api/projects/{project_id}/documents", files={"file": (filename, data)}, data=form)


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    return doc.tobytes()
