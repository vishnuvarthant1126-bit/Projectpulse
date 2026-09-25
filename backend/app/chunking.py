"""Split sections into overlapping chunks, preferring paragraph/line/sentence boundaries.

Chunks never cross a section, so each keeps a single heading and page number.
Offsets are relative to the section text so the source viewer can highlight them.
"""

from __future__ import annotations

from dataclasses import dataclass

_BOUNDARIES = ("\n\n", "\n", ". ", "; ", ", ", " ")


@dataclass
class ChunkSpan:
    start: int
    end: int
    text: str


def _find_break(text: str, start: int, end: int, min_len: int) -> int:
    """Return the best end position <= end that falls on a natural boundary."""
    window = text[start:end]
    for sep in _BOUNDARIES:
        idx = window.rfind(sep)
        if idx >= min_len:
            return start + idx + len(sep)
    return end


def split_text(text: str, chunk_size: int, overlap: int) -> list[ChunkSpan]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(overlap, chunk_size // 2))
    n = len(text)
    if n <= chunk_size:
        return [ChunkSpan(0, n, text)] if text.strip() else []

    spans: list[ChunkSpan] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            end = _find_break(text, start, end, min_len=int(chunk_size * 0.6))
        piece = text[start:end]
        if piece.strip():
            # trim surrounding whitespace but keep offsets exact
            lstrip = len(piece) - len(piece.lstrip())
            rstrip = len(piece) - len(piece.rstrip())
            spans.append(ChunkSpan(start + lstrip, end - rstrip, piece.strip()))
        if end >= n:
            break
        nxt = max(end - overlap, start + 1)
        # move forward to the start of a word so chunks don't begin mid-word
        while 0 < nxt < end and not text[nxt - 1].isspace():
            nxt += 1
        start = nxt if nxt < end else end
    return spans


def index_text(doc_title: str | None, heading: str | None, text: str) -> str:
    """Text used for BM25 and embeddings. The document title and section heading give
    each chunk context it would otherwise lose (e.g. "Steering Committee" / "Blockers")."""
    parts = [p for p in (doc_title, heading) if p]
    if len(parts) == 2 and parts[0] == parts[1]:
        parts = parts[:1]
    context = " | ".join(parts)
    return f"{context}\n{text}" if context else text
