"""ProjectPulse HTTP API (FastAPI).

Local, single-user MVP: there is no authentication, so the API must not be exposed
publicly. Docker Compose binds it to the internal network only; the Next.js server
proxies browser requests to it so API keys never reach the browser.
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import ingest
from .config import get_settings
from .demo import ensure_sample_project, precomputed_entries
from .models import (
    AskRequest,
    AskResponse,
    ChunkRef,
    DocType,
    Document,
    DocumentContent,
    DocumentUpdate,
    Project,
    ProjectCreate,
    SearchRequest,
    SearchResponse,
    SectionOut,
)
from .qa import ask
from .ratelimit import RateLimiter
from .services import Services, build_services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

GENERIC_QUESTIONS = [
    "What changed between the original plan and the latest update?",
    "Which milestones are delayed, and what caused the delays?",
    "What blockers remain unresolved?",
    "Which decisions or tasks need attention?",
]


def create_app(services: Services | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services is None:
            app.state.services = build_services(get_settings())
        if app.state.services.settings.public_demo:
            ensure_sample_project(app.state.services)  # visitors land on a ready sample project
        yield

    app = FastAPI(title="ProjectPulse API", version="0.1.0", lifespan=lifespan)
    if services is not None:
        app.state.services = services
    settings = services.settings if services else get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type"],
    )

    def svc(request: Request) -> Services:
        return request.app.state.services

    Svc = Annotated[Services, Depends(svc)]
    limiter = RateLimiter(settings.ask_rate_per_client_per_min, settings.ask_rate_global_per_min)

    def writable(request: Request) -> None:
        """Block every change to projects or documents in the public demo."""
        if request.app.state.services.settings.public_demo:
            raise HTTPException(403, "This is a read-only public demo. Run ProjectPulse locally to upload documents.")

    Writable = Depends(writable)

    def client_key(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")

    def get_project(s: Services, project_id: str) -> dict:
        p = s.db.one("SELECT * FROM projects WHERE id = ?", (project_id,))
        if p and s.settings.public_demo and not p["is_sample"]:
            p = None
        if not p:
            raise HTTPException(404, "Project not found.")
        return p

    def project_out(s: Services, p: dict) -> Project:
        n = s.db.one("SELECT COUNT(*) AS n FROM documents WHERE project_id = ?", (p["id"],))["n"]
        return Project(**{**p, "is_sample": bool(p["is_sample"])}, document_count=n)

    def doc_out(d: dict) -> Document:
        return Document(**{k: d[k] for k in Document.model_fields})

    @app.exception_handler(ingest.UploadError)
    async def upload_error(_: Request, exc: ingest.UploadError):
        body = {"detail": str(exc)}
        if exc.existing:
            body["existing_document_id"] = exc.existing["id"]
        return JSONResponse(body, status_code=exc.status_code)

    # ---------------------------------------------------------------- meta

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/config")
    def config(s: Svc) -> dict:
        st = s.settings
        return {
            "llm_enabled": s.llm is not None,
            "llm_provider": st.llm_provider if s.llm else None,
            "llm_model": s.llm.name if s.llm else None,
            "embedding_model": s.embedder.name,
            "demo_mode": s.llm is None,
            "public_demo": st.public_demo,
            "max_upload_mb": st.max_upload_mb,
            "allowed_extensions": list(st.allowed_extensions),
            "retrieval": {
                "candidates_per_retriever": st.retrieval_candidates,
                "answer_max_passages": st.answer_max_passages,
                "rrf_k": st.rrf_k,
                "chunk_size": st.chunk_size,
                "chunk_overlap": st.chunk_overlap,
            },
        }

    # ------------------------------------------------------------- projects

    @app.get("/api/projects", response_model=list[Project])
    def list_projects(s: Svc):
        where = "WHERE is_sample = 1" if s.settings.public_demo else ""
        return [
            project_out(s, p)
            for p in s.db.query(f"SELECT * FROM projects {where} ORDER BY is_sample DESC, created_at DESC")
        ]

    @app.post("/api/projects", response_model=Project, status_code=201, dependencies=[Writable])
    def create_project(body: ProjectCreate, s: Svc):
        return project_out(s, ingest.create_project(s, body.name, body.description))

    @app.post("/api/projects/sample", response_model=Project)
    def sample_project(s: Svc, reset: bool = False):
        if reset and s.settings.public_demo:
            raise HTTPException(403, "Resetting the sample project is disabled in the public demo.")
        return project_out(s, ensure_sample_project(s, reset=reset))

    @app.get("/api/projects/{project_id}", response_model=Project)
    def read_project(project_id: str, s: Svc):
        return project_out(s, get_project(s, project_id))

    @app.delete("/api/projects/{project_id}", status_code=204, dependencies=[Writable])
    def remove_project(project_id: str, s: Svc):
        if not ingest.delete_project(s, project_id):
            raise HTTPException(404, "Project not found.")

    @app.get("/api/projects/{project_id}/suggested-questions")
    def suggested(project_id: str, s: Svc) -> dict:
        p = get_project(s, project_id)
        if p["is_sample"]:
            qs = [e["question"] for e in precomputed_entries(s)]
            return {"questions": qs, "precomputed": s.llm is None}
        return {"questions": GENERIC_QUESTIONS, "precomputed": False}

    # ------------------------------------------------------------ documents

    @app.get("/api/projects/{project_id}/documents", response_model=list[Document])
    def list_documents(project_id: str, s: Svc):
        get_project(s, project_id)
        rows = s.db.query(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY COALESCE(reporting_date, '9999'), created_at",
            (project_id,),
        )
        return [doc_out(d) for d in rows]

    @app.post("/api/projects/{project_id}/documents", response_model=Document, status_code=202, dependencies=[Writable])
    async def upload_document(
        project_id: str,
        s: Svc,
        background: BackgroundTasks,
        file: UploadFile = File(...),
        doc_type: DocType = Form("other"),
        reporting_date: str | None = Form(None),
    ):
        get_project(s, project_id)
        if reporting_date:
            try:
                reporting_date = DocumentUpdate(reporting_date=reporting_date).reporting_date.isoformat()
            except Exception as exc:
                raise HTTPException(422, "reporting_date must be a valid date (YYYY-MM-DD).") from exc
        max_bytes = int(s.settings.max_upload_mb * 1024 * 1024)
        data = await file.read(max_bytes + 1)  # never read more than the limit + 1 byte
        doc = ingest.create_document(s, project_id, file.filename or "document", data, doc_type, reporting_date)
        background.add_task(ingest.process_document, s, doc["id"])
        return doc_out(doc)

    @app.get("/api/documents/{document_id}", response_model=Document)
    def read_document(document_id: str, s: Svc):
        d = ingest.get_document(s, document_id)
        if not d:
            raise HTTPException(404, "Document not found.")
        return doc_out(d)

    @app.patch("/api/documents/{document_id}", response_model=Document, dependencies=[Writable])
    def patch_document(document_id: str, body: DocumentUpdate, s: Svc):
        d = ingest.update_document(
            s, document_id, body.doc_type, body.reporting_date.isoformat() if body.reporting_date else None
        )
        return doc_out(d)

    @app.delete("/api/documents/{document_id}", status_code=204, dependencies=[Writable])
    def remove_document(document_id: str, s: Svc):
        if not ingest.delete_document(s, document_id):
            raise HTTPException(404, "Document not found.")

    @app.get("/api/documents/{document_id}/content", response_model=DocumentContent)
    def document_content(document_id: str, s: Svc):
        d = ingest.get_document(s, document_id)
        if not d:
            raise HTTPException(404, "Document not found.")
        sections = s.db.query(
            "SELECT id, ordinal, heading, page, text FROM sections WHERE document_id = ? ORDER BY ordinal",
            (document_id,),
        )
        chunks = s.db.query(
            "SELECT id, section_id, char_start, char_end, page FROM chunks WHERE document_id = ? ORDER BY ordinal",
            (document_id,),
        )
        return DocumentContent(
            document=doc_out(d),
            sections=[SectionOut(**x) for x in sections],
            chunks=[ChunkRef(**c) for c in chunks],
        )

    # ------------------------------------------------------------- retrieval

    @app.post("/api/projects/{project_id}/search", response_model=SearchResponse)
    def search(project_id: str, body: SearchRequest, s: Svc):
        get_project(s, project_id)
        ranked = s.retriever.rank(project_id, body.query, body.mode)[: body.k]
        from .retrieval import detect_intents

        return SearchResponse(
            mode=body.mode, intents=detect_intents(body.query), passages=s.retriever.to_passages(project_id, ranked)
        )

    @app.post("/api/projects/{project_id}/ask", response_model=AskResponse)
    def ask_question(project_id: str, body: AskRequest, s: Svc, request: Request):
        project = get_project(s, project_id)
        if s.settings.public_demo and not limiter.allow(client_key(request)):
            raise HTTPException(429, "Too many questions right now. Please wait a minute and try again.")
        return ask(s, project, body.question, body.mode)

    return app


app = create_app()
