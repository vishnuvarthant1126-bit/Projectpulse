"""Public demo mode: read-only sample project, rate-limited questions."""

import pytest
from fastapi.testclient import TestClient

from app.embeddings import HashEmbedder
from app.main import create_app
from app.ratelimit import RateLimiter
from app.services import build_services

from .conftest import make_pdf


@pytest.fixture
def demo_client(settings):
    settings.public_demo = True
    settings.ask_rate_per_client_per_min = 3
    svc = build_services(settings, embedder=HashEmbedder())
    with TestClient(create_app(svc)) as c:
        yield c
    svc.db.close()


def test_sample_project_is_preloaded_and_only_project_listed(demo_client):
    projects = demo_client.get("/api/projects").json()
    assert len(projects) == 1 and projects[0]["is_sample"] and projects[0]["document_count"] == 6
    assert demo_client.get("/api/config").json()["public_demo"] is True


def test_all_writes_are_blocked(demo_client):
    pid = demo_client.get("/api/projects").json()[0]["id"]
    doc = demo_client.get(f"/api/projects/{pid}/documents").json()[0]
    assert demo_client.post("/api/projects", json={"name": "x"}).status_code == 403
    assert demo_client.delete(f"/api/projects/{pid}").status_code == 403
    assert demo_client.post("/api/projects/sample?reset=true").status_code == 403
    up = demo_client.post(
        f"/api/projects/{pid}/documents",
        files={"file": ("a.pdf", make_pdf(["hello world"]))},
        data={"doc_type": "other"},
    )
    assert up.status_code == 403
    assert demo_client.patch(f"/api/documents/{doc['id']}", json={"doc_type": "other"}).status_code == 403
    assert demo_client.delete(f"/api/documents/{doc['id']}").status_code == 403
    assert len(demo_client.get(f"/api/projects/{pid}/documents").json()) == 6


def test_reads_and_questions_still_work_then_rate_limit(demo_client):
    pid = demo_client.get("/api/projects").json()[0]["id"]
    q = {"question": "What blockers remain unresolved?"}
    headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
    codes = [demo_client.post(f"/api/projects/{pid}/ask", json=q, headers=headers).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    # a different client is not affected
    other = {"x-forwarded-for": "198.51.100.9"}
    assert demo_client.post(f"/api/projects/{pid}/ask", json=q, headers=other).status_code == 200


def test_rate_limiter_global_cap():
    rl = RateLimiter(per_client=0, global_limit=2)
    assert rl.allow("a") and rl.allow("b") and not rl.allow("c")
