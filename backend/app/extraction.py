"""Text extraction for PDF (PyMuPDF), Markdown and plain text.

Output is a list of *sections*: contiguous text under one heading on one page.
A heading that runs across a PDF page break becomes two sections with the same
heading, so every chunk derived from a section has exactly one page number.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import pymupdf


class ExtractionError(Exception):
    """A user-facing explanation of why a document could not be processed."""


@dataclass
class Section:
    heading: str | None
    page: int | None  # 1-based PDF page; None for MD/TXT
    text: str


@dataclass
class Extracted:
    sections: list[Section]
    page_count: int | None


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # also expands ligatures such as "ﬁ"
    text = text.replace(" ", " ").replace("•", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- PDF


def extract_pdf(data: bytes, min_chars_per_page: int = 25) -> Extracted:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # corrupted file, wrong type
        raise ExtractionError("This file could not be opened as a PDF. It may be corrupted.") from exc
    if doc.needs_pass:
        raise ExtractionError("This PDF is password-protected. Remove the password and upload it again.")
    if doc.page_count == 0:
        raise ExtractionError("This PDF has no pages.")

    # First pass: collect lines with their max font size to find the body size.
    pages: list[list[tuple[float, str]]] = []
    size_weights: Counter[float] = Counter()
    total_chars = 0
    for page in doc:
        lines: list[tuple[float, str]] = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    continue
                size = round(max(span["size"] for span in line["spans"]), 1)
                lines.append((size, text))
                size_weights[size] += len(text)
                total_chars += len(text)
        pages.append(lines)

    if total_chars / doc.page_count < min_chars_per_page:
        raise ExtractionError(
            "No extractable text was found. This looks like a scanned or image-only PDF. "
            "OCR is not supported in this MVP, so please upload a text-based PDF, Markdown or TXT version."
        )

    body_size = size_weights.most_common(1)[0][0]
    sections: list[Section] = []
    heading: str | None = None

    def flush(buf: list[str], heading: str | None, page_no: int) -> None:
        text = _clean("\n".join(buf))
        if text:
            sections.append(Section(heading=heading, page=page_no, text=text))
        buf.clear()

    for page_no, lines in enumerate(pages, start=1):
        buf: list[str] = []
        for size, text in lines:
            is_heading = size >= body_size * 1.2 and len(text) <= 120
            if is_heading:
                flush(buf, heading, page_no)
                heading = _clean(text)
            else:
                buf.append(text)
        flush(buf, heading, page_no)
    return Extracted(sections=sections, page_count=doc.page_count)


# ---------------------------------------------------------------------- Markdown

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def extract_markdown(text: str) -> Extracted:
    sections: list[Section] = []
    heading: str | None = None
    buf: list[str] = []
    in_code = False

    def flush() -> None:
        body = _clean("\n".join(buf))
        if body:
            sections.append(Section(heading=heading, page=None, text=body))
        buf.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            buf.append(line)
            continue
        m = None if in_code else _MD_HEADING.match(line)
        if m:
            flush()
            heading = _clean(m.group(2))
        else:
            buf.append(line)
    flush()
    if not sections and heading:
        # A document that is only headings still has searchable text.
        sections.append(Section(heading=heading, page=None, text=heading))
    return Extracted(sections=sections, page_count=None)


# -------------------------------------------------------------------------- Text


def _looks_like_heading(line: str, next_line: str | None) -> bool:
    s = line.strip()
    if not s or len(s) > 80 or s.endswith((".", ",", ";")):
        return False
    if next_line is not None and re.fullmatch(r"[=\-]{3,}", next_line.strip()):
        return True  # setext-style underline
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and len(letters) >= 3 and all(c.isupper() for c in letters)


def extract_text(text: str) -> Extracted:
    if any(line.lstrip().startswith("#") for line in text.splitlines()):
        return extract_markdown(text)
    lines = text.splitlines()
    sections: list[Section] = []
    heading: str | None = None
    buf: list[str] = []
    skip_next = False

    def flush() -> None:
        body = _clean("\n".join(buf))
        if body:
            sections.append(Section(heading=heading, page=None, text=body))
        buf.clear()

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if _looks_like_heading(line, nxt):
            flush()
            heading = _clean(line)
            skip_next = nxt is not None and bool(re.fullmatch(r"[=\-]{3,}", nxt.strip()))
        else:
            buf.append(line)
    flush()
    return Extracted(sections=sections, page_count=None)


def decode_text(data: bytes) -> str:
    if b"\x00" in data:
        raise ExtractionError("This file contains binary data and is not a valid text or Markdown file.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("Text and Markdown files must be UTF-8 encoded.") from exc


def extract(data: bytes, ext: str, min_chars_per_pdf_page: int = 25) -> Extracted:
    ext = ext.lower()
    if ext == ".pdf":
        result = extract_pdf(data, min_chars_per_pdf_page)
    elif ext in (".md", ".markdown"):
        result = extract_markdown(decode_text(data))
    elif ext == ".txt":
        result = extract_text(decode_text(data))
    else:
        raise ExtractionError(f"Unsupported file type: {ext}")
    if not result.sections or not any(s.text.strip() for s in result.sections):
        raise ExtractionError("The document is empty: no text could be extracted.")
    return result
