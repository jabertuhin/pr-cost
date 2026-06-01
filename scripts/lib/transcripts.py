"""Parse Claude Code transcript JSONL into compact usage records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class UsageRecord:
    uuid: str
    session_id: str
    timestamp: str
    git_branch: str
    cwd: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


def iter_usage(transcript_path: Path) -> Iterator[UsageRecord]:
    """Yield one UsageRecord per assistant message line with token usage."""
    with transcript_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                line = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rec = _to_record(line)
            if rec is not None:
                yield rec


def _to_record(line: dict) -> UsageRecord | None:
    if line.get("type") != "assistant":
        return None
    msg = line.get("message") or {}
    usage = msg.get("usage") or {}
    if not usage:
        return None
    model = usage.get("model") or msg.get("model") or ""
    if not model:
        return None
    return UsageRecord(
        uuid=line.get("uuid", ""),
        session_id=line.get("sessionId", ""),
        timestamp=line.get("timestamp", ""),
        git_branch=line.get("gitBranch") or "",
        cwd=line.get("cwd") or "",
        model=model,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_creation_input_tokens=int(usage.get("cache_creation_input_tokens") or 0),
        cache_read_input_tokens=int(usage.get("cache_read_input_tokens") or 0),
    )
