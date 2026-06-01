"""Read and group per-branch aggregate JSONL."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelTotals:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0


@dataclass
class BranchTotals:
    by_model: dict[str, ModelTotals] = field(default_factory=dict)
    sessions: set[str] = field(default_factory=set)
    turns: int = 0

    def add(self, entry: dict) -> None:
        model = entry.get("model", "")
        m = self.by_model.setdefault(model, ModelTotals())
        m.input += int(entry.get("in", 0))
        m.output += int(entry.get("out", 0))
        m.cache_write += int(entry.get("cc", 0))
        m.cache_read += int(entry.get("cr", 0))
        s = entry.get("session", "")
        if s:
            self.sessions.add(s)
        self.turns += 1


def aggregate_file(path: Path) -> BranchTotals:
    totals = BranchTotals()
    if not path.exists():
        return totals
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            totals.add(entry)
    return totals


def append_entry(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
