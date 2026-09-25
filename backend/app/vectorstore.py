"""Chroma vector store. Each project gets its own collection, so semantic search is
physically isolated per project (not just filtered). Embeddings are computed by our
own Embedder, so Chroma never downloads a default embedding model."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    def __init__(self, path: Path, embedder_name: str):
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True)
        )
        # Collections are namespaced by embedder so switching models never mixes vector spaces.
        self.model_tag = hashlib.sha1(embedder_name.encode()).hexdigest()[:8]

    def _name(self, project_id: str) -> str:
        return f"p_{project_id.replace('-', '')}_{self.model_tag}"

    def _collection(self, project_id: str):
        return self.client.get_or_create_collection(
            name=self._name(project_id),
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"project_id": project_id},
        )

    def add(
        self, project_id: str, ids: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]]
    ) -> None:
        if not ids:
            return
        col = self._collection(project_id)
        col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def query(
        self, project_id: str, embedding: list[float], n: int, where: dict[str, Any] | None = None
    ) -> list[tuple[str, float]]:
        col = self._collection(project_id)
        count = col.count()
        if count == 0:
            return []
        res = col.query(
            query_embeddings=[embedding], n_results=min(n, count), where=where or None, include=["distances"]
        )
        ids = res["ids"][0]
        dists = res["distances"][0] if res.get("distances") else [0.0] * len(ids)
        return [(i, 1.0 - float(d)) for i, d in zip(ids, dists, strict=False)]  # cosine similarity

    def update_metadata(self, project_id: str, document_id: str, metadata: dict[str, Any]) -> None:
        col = self._collection(project_id)
        got = col.get(where={"document_id": document_id}, include=[])
        if got["ids"]:
            col.update(ids=got["ids"], metadatas=[metadata] * len(got["ids"]))

    def delete_document(self, project_id: str, document_id: str) -> None:
        self._collection(project_id).delete(where={"document_id": document_id})

    def count_document(self, project_id: str, document_id: str) -> int:
        return len(self._collection(project_id).get(where={"document_id": document_id}, include=[])["ids"])

    def delete_project(self, project_id: str) -> None:
        try:
            self.client.delete_collection(self._name(project_id))
        except Exception:
            pass  # already absent
