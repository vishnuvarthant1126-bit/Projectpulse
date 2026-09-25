"""Service container wired once at startup (and by tests with overrides)."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .db import Database
from .embeddings import Embedder, build_embedder
from .keyword import KeywordIndex
from .llm import LLM, build_llm
from .retrieval import Retriever
from .vectorstore import VectorStore


@dataclass
class Services:
    settings: Settings
    db: Database
    embedder: Embedder
    vectors: VectorStore
    keyword: KeywordIndex
    retriever: Retriever
    llm: LLM | None


def build_services(settings: Settings, embedder: Embedder | None = None, llm: LLM | None = None) -> Services:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    emb = embedder or build_embedder(settings)
    vectors = VectorStore(settings.chroma_dir, emb.name)
    keyword = KeywordIndex()
    retriever = Retriever(settings, db, emb, vectors, keyword)
    return Services(settings, db, emb, vectors, keyword, retriever, llm if llm is not None else build_llm(settings))
