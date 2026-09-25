"""BM25 keyword retrieval over a project's ready chunks.

Okapi BM25 (k1=1.5, b=0.75) with the Lucene-style IDF, log(1 + (N - n + 0.5) / (n + 0.5)),
which stays positive for small corpora. (The classic Okapi IDF is zero or negative for a
term that appears in half or more of the chunks, which breaks projects with only one or
two short documents.)

The index is built in memory per project and cached until that project's documents
change. Tokenisation keeps identifiers such as "BCN-201" or "M2" intact *and* indexes
their parts, so both "BCN-201" and "BCN 201" match.
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter
from dataclasses import dataclass

STOPWORDS = frozenset(
    """a an and are as at be been but by did do does for from had has have how i if in into is it its
    of on or our s so than that the their them then there these they this to was we were what when
    where which who whom why will with would you your about any can could should""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+(?:[-_./][a-z0-9]+)*")


def _stem(tok: str) -> str:
    # Deliberately light: plural/verb suffixes only, so identifiers stay intact.
    if tok.isdigit() or len(tok) <= 3 or any(c.isdigit() for c in tok):
        return tok
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)] + rep
    return tok


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for m in _TOKEN.finditer(text.lower()):
        tok = m.group(0)
        parts = re.split(r"[-_./]", tok)
        if len(parts) > 1:
            out.append(tok)  # compound identifier, e.g. "bcn-201"
        for p in parts:
            if p and p not in STOPWORDS:
                out.append(_stem(p))
    return out


class BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(doc) for doc in corpus]
        self.len = [len(doc) for doc in corpus]
        self.avgdl = (sum(self.len) / len(corpus)) if corpus else 0.0
        df: Counter[str] = Counter()
        for doc in self.tf:
            df.update(doc.keys())
        n = len(corpus)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def get_scores(self, query: list[str]) -> list[float]:
        scores = [0.0] * len(self.tf)
        for term in set(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(term)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avgdl or 1))
                    scores[i] += idf * f * (self.k1 + 1) / denom
        return scores


@dataclass
class _Index:
    version: int
    ids: list[str]
    bm25: BM25 | None
    doc_types: list[str]
    document_ids: list[str]


class KeywordIndex:
    def __init__(self) -> None:
        self._cache: dict[str, _Index] = {}
        self._versions: dict[str, int] = {}
        self._lock = threading.Lock()

    def invalidate(self, project_id: str) -> None:
        with self._lock:
            self._versions[project_id] = self._versions.get(project_id, 0) + 1

    def _get(self, project_id: str, loader) -> _Index:
        with self._lock:
            version = self._versions.get(project_id, 0)
            idx = self._cache.get(project_id)
            if idx is not None and idx.version == version:
                return idx
        rows = loader(project_id)  # [(chunk_id, index_text, doc_type, document_id)]
        tokens = [tokenize(r[1]) for r in rows]
        bm25 = BM25(tokens) if rows and any(tokens) else None
        idx = _Index(version, [r[0] for r in rows], bm25, [r[2] for r in rows], [r[3] for r in rows])
        with self._lock:
            if self._versions.get(project_id, 0) == version:
                self._cache[project_id] = idx
        return idx

    def search(
        self,
        project_id: str,
        query: str,
        n: int,
        loader,
        doc_types: set[str] | None = None,
        document_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        idx = self._get(project_id, loader)
        q = tokenize(query)
        if idx.bm25 is None or not q:
            return []
        scores = idx.bm25.get_scores(q)
        ranked = sorted(
            (
                (idx.ids[i], float(s))
                for i, s in enumerate(scores)
                if s > 0
                and (doc_types is None or idx.doc_types[i] in doc_types)
                and (document_ids is None or idx.document_ids[i] in document_ids)
            ),
            key=lambda t: (-t[1], t[0]),
        )
        return ranked[:n]
