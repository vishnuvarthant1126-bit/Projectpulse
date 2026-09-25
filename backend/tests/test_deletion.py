"""Deleting a document (or project) removes its searchable chunks everywhere."""

from .conftest import make_project, upload

DOC = "# Weekly report\n\nThe quasar pipeline shipped on 5 March 2026 after the load test passed."
OTHER = "# Other report\n\nThe nebula dashboard beta is on track for 27 March 2026."


def test_delete_document_removes_chunks_vectors_and_keyword_hits(client, services, settings):
    pid = make_project(client)
    doc = upload(client, pid, "report.md", DOC).json()
    keep = upload(client, pid, "other.md", OTHER).json()
    assert client.get(f"/api/documents/{doc['id']}").json()["status"] == "ready"
    assert services.vectors.count_document(pid, doc["id"]) > 0
    hits = client.post(f"/api/projects/{pid}/search", json={"query": "quasar pipeline", "mode": "keyword"}).json()
    assert any(p["document_id"] == doc["id"] for p in hits["passages"])

    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204

    assert client.get(f"/api/documents/{doc['id']}").status_code == 404
    assert services.db.query("SELECT id FROM chunks WHERE document_id = ?", (doc["id"],)) == []
    assert services.db.query("SELECT id FROM sections WHERE document_id = ?", (doc["id"],)) == []
    assert services.vectors.count_document(pid, doc["id"]) == 0
    assert not (settings.uploads_dir / pid / f"{doc['id']}.md").exists()
    for mode in ("keyword", "semantic", "hybrid"):
        res = client.post(f"/api/projects/{pid}/search", json={"query": "quasar pipeline shipped", "mode": mode}).json()
        assert all(p["document_id"] != doc["id"] for p in res["passages"]), mode
    # the other document is untouched
    assert services.vectors.count_document(pid, keep["id"]) > 0


def test_reupload_after_delete_is_not_a_duplicate(client):
    pid = make_project(client)
    doc = upload(client, pid, "report.md", DOC).json()
    client.delete(f"/api/documents/{doc['id']}")
    assert upload(client, pid, "report.md", DOC).status_code == 202


def test_delete_project_removes_everything(client, services):
    pid = make_project(client)
    doc = upload(client, pid, "report.md", DOC).json()
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert services.db.query("SELECT id FROM chunks WHERE project_id = ?", (pid,)) == []
    assert services.db.query("SELECT id FROM documents WHERE id = ?", (doc["id"],)) == []


def test_delete_missing_document_is_404(client):
    assert client.delete("/api/documents/does-not-exist").status_code == 404
