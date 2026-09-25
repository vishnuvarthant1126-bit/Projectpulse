"""Embedding providers.

- local:  a sentence-transformers ONNX export run with onnxruntime (default:
          all-MiniLM-L6-v2, mean pooling, L2-normalised). Runs offline once the model
          files are downloaded with `python backend/scripts/download_model.py`.
- openai: any OpenAI-compatible /embeddings endpoint (model name configurable).
- hash:   deterministic feature hashing. For tests only; it is not semantic.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from .config import Settings


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalOnnxEmbedder:
    def __init__(self, model_dir: Path, model_name: str, batch_size: int = 32, max_length: int = 256):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_path = model_dir / "onnx" / "model.onnx"
        if not model_path.exists():
            model_path = model_dir / "model.onnx"
        tok_path = model_dir / "tokenizer.json"
        if not model_path.exists() or not tok_path.exists():
            raise RuntimeError(
                f"Local embedding model not found in {model_dir}. "
                "Run `python backend/scripts/download_model.py` or set EMBEDDING_PROVIDER=openai."
            )
        self.name = f"local:{model_name}"
        self.batch_size = batch_size
        self.tokenizer = Tokenizer.from_file(str(tok_path))
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = self.tokenizer.encode_batch(texts[i : i + self.batch_size])
            ids = np.array([e.ids for e in batch], dtype=np.int64)
            mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feeds["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feeds)[0]  # (batch, seq, dim)
            m = mask[..., None].astype(np.float32)
            pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
            pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
            out.extend(pooled.astype(float).tolist())
        return out


class OpenAIEmbedder:
    def __init__(self, base_url: str, api_key: str, model: str, batch_size: int = 64, timeout: float = 60.0):
        self.name = f"openai:{model}"
        self.url = base_url.rstrip("/") + "/embeddings"
        self.model = model
        self.batch_size = batch_size
        self.client = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            resp = self.client.post(self.url, json={"model": self.model, "input": texts[i : i + self.batch_size]})
            if resp.status_code >= 400:
                raise RuntimeError(f"Embedding API error {resp.status_code}")
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in data)
        return out


class HashEmbedder:
    """Bag-of-words feature hashing. Deterministic and fast; used by the test-suite."""

    def __init__(self, dim: int = 256):
        self.name = f"hash:{dim}"
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
            n = np.linalg.norm(v)
            out.append((v / n if n else v).tolist())
        return out


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "hash":
        return HashEmbedder()
    if settings.embedding_provider == "openai":
        if not settings.embedding_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requires EMBEDDING_API_KEY")
        return OpenAIEmbedder(
            settings.embedding_base_url,
            settings.embedding_api_key.get_secret_value(),
            settings.embedding_model,
            timeout=settings.llm_timeout_s,
        )
    return LocalOnnxEmbedder(settings.embedding_model_dir, settings.embedding_model, settings.embedding_batch_size)
