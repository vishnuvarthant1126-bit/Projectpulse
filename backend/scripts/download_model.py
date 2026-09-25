"""Download the local embedding model (sentence-transformers/all-MiniLM-L6-v2, ONNX export)
from Hugging Face into models/all-MiniLM-L6-v2/ (or EMBEDDING_MODEL_DIR).

    python backend/scripts/download_model.py

Only two files are needed: onnx/model.onnx and tokenizer.json. The script prints their
SHA-256 so you can compare them with the hashes recorded in the README for the
evaluation run.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import httpx

REPO = os.getenv("EMBEDDING_HF_REPO", "sentence-transformers/all-MiniLM-L6-v2")
REVISION = os.getenv("EMBEDDING_HF_REVISION", "main")
FILES = ["onnx/model.onnx", "tokenizer.json"]
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "models" / "all-MiniLM-L6-v2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    target = Path(os.getenv("EMBEDDING_MODEL_DIR", DEFAULT_DIR))
    for name in FILES:
        dest = target / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"exists  {dest}  sha256={sha256(dest)}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        print(f"fetch   {url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
            if r.status_code != 200:
                print(f"error: HTTP {r.status_code} for {url}", file=sys.stderr)
                return 1
            with tmp.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        tmp.rename(dest)
        print(f"saved   {dest}  sha256={sha256(dest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
