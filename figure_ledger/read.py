"""Read figure-ledger JSONL into events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Event:
    type: str
    text: str


def read_events(path: Path) -> list[Event]:
    return parse_events(path.read_text(encoding="utf-8"), str(path))


def parse_events(text: str, label: str) -> list[Event]:
    events: list[Event] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}:{line_number}: invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
            raise ValueError(f"{label}:{line_number}: each event needs a type")
        kind = payload["type"]
        if kind == "tool":
            output = payload.get("output")
            if not isinstance(output, str):
                raise ValueError(f"{label}:{line_number}: tool output must be a string")
            events.append(Event("tool", output))
        elif kind in {"assistant", "user"}:
            body = payload.get("text")
            if not isinstance(body, str):
                raise ValueError(f"{label}:{line_number}: {kind} text must be a string")
            events.append(Event(kind, body))
        else:
            raise ValueError(f"{label}:{line_number}: unknown type {kind}")
    return events
