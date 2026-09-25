"""Upload validation, processing status, reporting-date confirmation and extraction."""

from app.dates import detect_reporting_date
from app.extraction import extract

from .conftest import make_pdf, make_project, upload


def test_rejects_unsupported_type(client):
    pid = make_project(client)
    r = upload(client, pid, "sheet.xlsx", b"PK\x03\x04data")
    assert r.status_code == 415 and "Unsupported file type" in r.json()["detail"]


def test_rejects_fake_pdf(client):
    pid = make_project(client)
    assert upload(client, pid, "fake.pdf", b"hello, not a pdf").status_code == 415


def test_rejects_oversized_file(client):
    pid = make_project(client)  # test settings: 1 MB limit
    r = upload(client, pid, "big.txt", "a" * (1024 * 1024 + 10))
    assert r.status_code == 413


def test_rejects_empty_and_binary_text(client):
    pid = make_project(client)
    assert upload(client, pid, "empty.md", b"").status_code == 400
    assert upload(client, pid, "bin.txt", b"abc\x00\x01def").status_code == 415


def test_scanned_pdf_fails_with_ocr_message(client):
    pid = make_project(client)
    doc = upload(client, pid, "scan.pdf", make_pdf(["", ""])).json()
    d = client.get(f"/api/documents/{doc['id']}").json()
    assert d["status"] == "failed"
    assert "OCR is not supported" in d["error"]


def test_upload_without_date_needs_review_and_does_not_use_upload_time(client):
    pid = make_project(client)
    doc = upload(
        client,
        pid,
        "notes.md",
        "# Standup\n\nMeeting date: 4 March 2026\n\nWe agreed things.",
        doc_type="meeting_notes",
        reporting_date=None,
    ).json()
    d = client.get(f"/api/documents/{doc['id']}").json()
    assert d["status"] == "needs_review"
    assert d["reporting_date"] is None  # never auto-filled
    assert d["detected_date"] == "2026-03-04"
    assert "Meeting date" in d["detected_date_source"]
    r = client.patch(f"/api/documents/{doc['id']}", json={"reporting_date": "2026-03-04", "doc_type": "meeting_notes"})
    assert r.json()["status"] == "ready" and r.json()["reporting_date"] == "2026-03-04"


def test_invalid_reporting_date_rejected(client):
    pid = make_project(client)
    assert upload(client, pid, "a.md", "# A\n\ntext", reporting_date="06/03/2026").status_code == 422


def test_pdf_pages_and_headings_are_preserved():
    pdf = make_pdf(["Intro text on page one about the project.", "Milestone M2 target 27 February 2026 on page two."])
    ex = extract(pdf, ".pdf")
    pages = {s.page for s in ex.sections}
    assert pages == {1, 2} and ex.page_count == 2
    assert any("M2" in s.text and s.page == 2 for s in ex.sections)


def test_markdown_and_text_headings():
    md = extract(b"# Title\n\nIntro\n\n## Blockers\n\nB-1 open", ".md")
    assert [s.heading for s in md.sections] == ["Title", "Blockers"]
    txt = extract(b"STATUS REPORT\n\nAll good.\n\nOpen Risks\n----------\nR1 vendor", ".txt")
    assert [s.heading for s in txt.sections] == ["STATUS REPORT", "Open Risks"]


def test_date_detection_prefers_labelled_dates():
    iso, src = detect_reporting_date("Created 1 January 2026\nWeek ending: Friday 6 March 2026", "r.md")
    assert iso == "2026-03-06" and "Week ending" in src
    iso, src = detect_reporting_date("No dates here", "status_2026-02-20.md")
    assert iso == "2026-02-20" and "file name" in src
    assert detect_reporting_date("nothing", "x.md") == (None, None)


def test_sample_project_endpoint_is_idempotent(client):
    a = client.post("/api/projects/sample").json()
    b = client.post("/api/projects/sample").json()
    assert a["id"] == b["id"] and a["is_sample"] and a["document_count"] == 6
    docs = client.get(f"/api/projects/{a['id']}/documents").json()
    assert all(d["status"] == "ready" and d["reporting_date"] for d in docs)
    qs = client.get(f"/api/projects/{a['id']}/suggested-questions").json()
    assert qs["precomputed"] is True and len(qs["questions"]) >= 5


def test_config_never_exposes_secrets(client):
    cfg = client.get("/api/config").json()
    assert "llm_api_key" not in str(cfg).lower() and "embedding_api_key" not in str(cfg).lower()
    assert cfg["demo_mode"] is True
