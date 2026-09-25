"""Date parsing helpers.

1. `detect_reporting_date` suggests a reporting date from document text or filename.
   The suggestion is only shown to the user; it is never applied without confirmation,
   and upload time is never used as a reporting date.
2. `find_dates` normalises dates mentioned in answer text so the backend can check
   that each date an answer states actually appears in the passages it cites.
"""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for m in names
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\.?,?\s+(20\d{{2}})\b", re.I)
_MDY = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d{{2}})\b", re.I)
# Dates without a year ("6 March", "March 6") are also checked in answers.
_DM = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\b(?!\.?,?\s+20\d{{2}})", re.I)
_MD = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!,?\s+20\d{{2}})(?!\d)", re.I)

_REPORT_HINT = re.compile(
    r"(week ending|report(?:ing)? date|meeting date|plan date|date of meeting|as of|dated?)\s*:?",
    re.I,
)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_full_dates(text: str) -> list[tuple[date, int, int]]:
    """All dates with an explicit year, with their character spans."""
    out: list[tuple[date, int, int]] = []
    for m in _ISO.finditer(text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            out.append((d, m.start(), m.end()))
    for m in _DMY.finditer(text):
        d = _safe_date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            out.append((d, m.start(), m.end()))
    for m in _MDY.finditer(text):
        d = _safe_date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            out.append((d, m.start(), m.end()))
    return sorted(out, key=lambda t: t[1])


def find_dates(text: str) -> set[tuple[int | None, int, int]]:
    """Normalised (year|None, month, day) tuples for every date mentioned in text."""
    found: set[tuple[int | None, int, int]] = {(d.year, d.month, d.day) for d, _, _ in find_full_dates(text)}
    for m in _DM.finditer(text):
        day, month = int(m.group(1)), MONTHS[m.group(2).lower()]
        if 1 <= day <= 31:
            found.add((None, month, day))
    for m in _MD.finditer(text):
        day, month = int(m.group(2)), MONTHS[m.group(1).lower()]
        if 1 <= day <= 31:
            found.add((None, month, day))
    return found


def date_supported(d: tuple[int | None, int, int], haystack: set[tuple[int | None, int, int]]) -> bool:
    year, month, day = d
    for y, m, dd in haystack:
        if m == month and dd == day and (year is None or y is None or y == year):
            return True
    return False


def detect_reporting_date(text: str, filename: str) -> tuple[str | None, str | None]:
    """Suggest a reporting date. Returns (iso_date, evidence_snippet)."""
    head = text[:3000]
    dates = find_full_dates(head)
    # Prefer a date that follows a hint such as "Week ending:" or "Meeting date:".
    for hint in _REPORT_HINT.finditer(head):
        for d, start, end in dates:
            if 0 <= start - hint.end() <= 40:
                snippet = head[hint.start() : end].replace("\n", " ").strip()
                return d.isoformat(), snippet[:120]
    m = _ISO.search(filename)
    if m:
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d.isoformat(), f"file name: {filename}"
    if dates:
        d, start, end = dates[0]
        return d.isoformat(), head[max(0, start - 30) : end].replace("\n", " ").strip()[:120]
    return None, None
