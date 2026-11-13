"""A figure counts only when the same value is in a tool result above the reply."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from figure_ledger.read import Event, parse_events, read_events

_FENCE = re.compile(r"```.*?```", re.DOTALL)

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_MONTH_NAME = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
)

_REF = re.compile(r"\b([A-Za-z]{2,8})-(\d{3,8})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_NAME})\s+(\d{{4}})\b")
_MDY = re.compile(rf"\b({_MONTH_NAME})\s+(\d{{1,2}}),?\s+(\d{{4}})\b")

_NUMBER = r"\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_BEFORE = r"ZAR|USD|EUR|GBP|NGN|[R$€£₦]"
_MONEY_BEFORE = re.compile(rf"(?<![A-Za-z])(?:{_BEFORE})\s*({_NUMBER})", re.IGNORECASE)
_MONEY_AFTER = re.compile(rf"(?<!\d)({_NUMBER})\s+(?:ZAR|USD|EUR|GBP|NGN)\b", re.IGNORECASE)
_COUNT = re.compile(r"\b(\d+)\s+(days?|hours?|minutes?|items?|parcels?|calls?)\b", re.IGNORECASE)

_COUNT_UNIT = {
    "day": "day",
    "days": "day",
    "hour": "hour",
    "hours": "hour",
    "minute": "minute",
    "minutes": "minute",
    "item": "item",
    "items": "item",
    "parcel": "parcel",
    "parcels": "parcel",
    "call": "call",
    "calls": "call",
}

_RANK = {"reference": 0, "date": 1, "money": 2, "count": 3}


@dataclass(frozen=True)
class Hit:
    kind: str
    start: int
    end: int
    surface: str
    value: str


@dataclass(frozen=True)
class Figure:
    kind: str
    surface: str
    value: str
    verdict: str
    earlier: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    path: str
    figures: tuple[Figure, ...]

    @property
    def integrity(self) -> str:
        sourced = sum(figure.verdict == "sourced" for figure in self.figures)
        return integrity_text(sourced, len(self.figures))


def score_path(path: Path) -> Report:
    return score_events(str(path), read_events(path))


def score_events(path: str, events: list[Event]) -> Report:
    earlier: dict[str, set[str]] = {kind: set() for kind in _RANK}
    figures: list[Figure] = []
    for event in events:
        if event.type == "tool":
            for hit in extract(event.text):
                earlier[hit.kind].add(hit.value)
            continue
        if event.type != "assistant":
            continue
        # Fenced blocks are examples. A figure inside one is not a claim.
        visible = _FENCE.sub(" ", event.text)
        for hit in extract(visible):
            known = earlier[hit.kind]
            # Sourced when this value is already in a tool result. Mismatch when
            # that kind came back with a different value. Orphan when it did not.
            if hit.value in known:
                verdict = "sourced"
            elif known:
                verdict = "mismatch"
            else:
                verdict = "orphan"
            figures.append(
                Figure(
                    kind=hit.kind,
                    surface=hit.surface,
                    value=hit.value,
                    verdict=verdict,
                    earlier=tuple(sorted(known)),
                )
            )
    return Report(path, tuple(figures))


def extract(text: str) -> tuple[Hit, ...]:
    hits: list[Hit] = []
    for match in _REF.finditer(text):
        value = f"{match.group(1).upper()}-{match.group(2)}"
        hits.append(Hit("reference", match.start(), match.end(), match.group(0), value))
    for match in _ISO.finditer(text):
        value = _iso(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if value:
            hits.append(Hit("date", match.start(), match.end(), match.group(0), value))
    for match in _DMY.finditer(text):
        month = _MONTHS.get(match.group(2).casefold())
        value = _iso(int(match.group(3)), month, int(match.group(1))) if month else None
        if value:
            hits.append(Hit("date", match.start(), match.end(), match.group(0), value))
    for match in _MDY.finditer(text):
        month = _MONTHS.get(match.group(1).casefold())
        value = _iso(int(match.group(3)), month, int(match.group(2))) if month else None
        if value:
            hits.append(Hit("date", match.start(), match.end(), match.group(0), value))
    for pattern in (_MONEY_BEFORE, _MONEY_AFTER):
        for match in pattern.finditer(text):
            value = _money(match.group(1))
            if value is not None:
                hits.append(Hit("money", match.start(), match.end(), match.group(0), value))
    for match in _COUNT.finditer(text):
        unit = _COUNT_UNIT[match.group(2).casefold()]
        value = f"{int(match.group(1))} {unit}"
        hits.append(Hit("count", match.start(), match.end(), match.group(0), value))

    hits.sort(key=lambda hit: (hit.start, _RANK[hit.kind], -hit.end))
    kept: list[Hit] = []
    cursor = -1
    for hit in hits:
        if hit.start < cursor:
            continue
        kept.append(hit)
        cursor = hit.end
    return tuple(kept)


def integrity_text(sourced: int, total: int) -> str:
    if total == 0:
        return "n/a"
    value = (Decimal(sourced) / Decimal(total)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{value:.3f}"


def format_table(reports: list[Report]) -> str:
    rows = [_cells(report.path, report.figures) for report in reports]
    combined = tuple(figure for report in reports for figure in report.figures)
    rows.append(_cells("TOTAL", combined))
    header = ("transcript", "figures", "sourced", "mismatch", "orphan", "integrity")
    widths = [max(len(header[index]), *(len(row[index]) for row in rows)) for index in range(6)]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    body = [line(header), line(tuple("-" * width for width in widths))]
    body.extend(line(row) for row in rows)
    return "\n".join(body)


def format_details(reports: list[Report]) -> str:
    blocks: list[str] = []
    for report in reports:
        lines = [report.path]
        if not report.figures:
            lines.append("  no figures")
        for figure in report.figures:
            earlier = ", ".join(figure.earlier) if figure.earlier else "none"
            lines.append(
                f"  {figure.verdict:<9}  {figure.kind:<9}  {figure.surface}  "
                f"value {figure.value}  earlier {earlier}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _cells(path: str, figures: tuple[Figure, ...]) -> tuple[str, str, str, str, str, str]:
    sourced = sum(figure.verdict == "sourced" for figure in figures)
    mismatch = sum(figure.verdict == "mismatch" for figure in figures)
    orphan = sum(figure.verdict == "orphan" for figure in figures)
    return (
        path,
        str(len(figures)),
        str(sourced),
        str(mismatch),
        str(orphan),
        integrity_text(sourced, len(figures)),
    )


def _money(raw: str) -> str | None:
    cleaned = raw.replace(" ", "").replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        return None
    whole, _, frac = cleaned.partition(".")
    frac = frac.rstrip("0")
    if frac:
        return f"{int(whole)}.{frac}"
    return str(int(whole))


def _iso(year: int, month: int | None, day: int) -> str | None:
    if month is None:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def score_text(body: str) -> Report:
    return score_events("inline", parse_events(body, "inline"))
