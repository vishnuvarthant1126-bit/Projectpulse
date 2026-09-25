"""Retrieval and answers must never cross project boundaries."""

import pytest

from app.qa import ask

from .conftest import make_project, upload

ALPHA = "# Alpha status\n\nThe zephyr gateway migration is blocked by ticket ALP-900. Owner: Rosa."
BETA = "# Beta status\n\nThe zephyr gateway migration finished early. Ticket BET-111 closed. Owner: Ken."


@pytest.fixture
def two_projects(client):
    a = make_project(client, "Alpha")
    b = make_project(client, "Beta")
    assert upload(client, a, "alpha.md", ALPHA).status_code == 202
    assert upload(client, b, "beta.md", BETA).status_code == 202
    return a, b


@pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
def test_search_only_returns_own_project(client, services, two_projects, mode):
    a, b = two_projects
    a_docs = {d["id"] for d in client.get(f"/api/projects/{a}/documents").json()}
    b_docs = {d["id"] for d in client.get(f"/api/projects/{b}/documents").json()}
    for pid, own, other in ((a, a_docs, b_docs), (b, b_docs, a_docs)):
        res = client.post(
            f"/api/projects/{pid}/search", json={"query": "zephyr gateway migration ticket owner", "mode": mode}
        )
        assert res.status_code == 200
        passages = res.json()["passages"]
        assert passages, "expected results in own project"
        assert {p["document_id"] for p in passages} <= own
        assert not ({p["document_id"] for p in passages} & other)


def test_identifier_from_other_project_is_not_found(client, two_projects):
    a, b = two_projects
    res = client.post(f"/api/projects/{b}/search", json={"query": "ALP-900", "mode": "keyword"})
    assert res.json()["passages"] == []


def test_ask_uses_only_selected_project(services, two_projects):
    a, _ = two_projects
    project = services.db.one("SELECT * FROM projects WHERE id = ?", (a,))
    r = ask(services, project, "Who owns the zephyr gateway migration?", "hybrid")
    assert r.passages
    assert all("Beta" not in p.text and p.document_name == "alpha.md" for p in r.passages)


def test_vector_collections_are_separate(services, two_projects):
    a, b = two_projects
    qvec = services.embedder.embed(["zephyr gateway"])[0]
    a_hits = {cid for cid, _ in services.vectors.query(a, qvec, 50)}
    b_hits = {cid for cid, _ in services.vectors.query(b, qvec, 50)}
    assert a_hits and b_hits and not (a_hits & b_hits)


def test_same_file_allowed_in_two_projects_but_not_twice_in_one(client):
    a = make_project(client, "A")
    b = make_project(client, "B")
    assert upload(client, a, "same.md", ALPHA).status_code == 202
    assert upload(client, b, "same.md", ALPHA).status_code == 202
    dup = upload(client, a, "renamed.md", ALPHA)
    assert dup.status_code == 409
    assert "Duplicate upload" in dup.json()["detail"]


def test_unknown_project_is_404(client):
    assert client.post("/api/projects/nope/search", json={"query": "x"}).status_code == 404
    assert client.post("/api/projects/nope/ask", json={"question": "x"}).status_code == 404
