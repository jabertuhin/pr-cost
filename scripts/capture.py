#!/usr/bin/env python3
"""Stop-hook entry: incrementally roll up transcript usage into a per-branch aggregate.

Reads the Stop-hook JSON payload from stdin (session_id, transcript_path, cwd).
Parses new lines in the transcript since the last cursor for this session, and
appends a compact entry to ~/.claude/pr-cost/usage/<repo-slug>/<branch>.jsonl
for each new assistant message with token usage.

This hook must never break the user's session. Any error → silent exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import aggregate, config, repo_id, transcripts  # noqa: E402


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    session_id = payload.get("session_id") or ""
    transcript_path = payload.get("transcript_path") or ""
    cwd_str = payload.get("cwd") or ""
    if not (session_id and transcript_path and cwd_str):
        return 0

    transcript = Path(os.path.expanduser(transcript_path))
    if not transcript.exists():
        return 0

    cfg = config.load()
    state_dir = config.expand(cfg["state_dir"])
    usage_dir = config.expand(cfg["usage_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    cursors_file = state_dir / "cursors.json"

    cursors = _read_cursors(cursors_file)
    last_uuid = cursors.get(session_id)

    slug = repo_id.slug_for(Path(cwd_str))
    branch_files: dict[str, Path] = {}
    latest_uuid = last_uuid
    seen_cursor = last_uuid is None  # if no prior cursor, start from beginning
    new_entries = 0

    for rec in transcripts.iter_usage(transcript):
        if not seen_cursor:
            if rec.uuid == last_uuid:
                seen_cursor = True
            continue
        if not rec.git_branch:
            continue
        branch_key = rec.git_branch
        path = branch_files.get(branch_key)
        if path is None:
            path = usage_dir / slug / f"{_safe_branch(branch_key)}.jsonl"
            branch_files[branch_key] = path
        aggregate.append_entry(
            path,
            {
                "ts": rec.timestamp,
                "session": session_id,
                "uuid": rec.uuid,
                "model": rec.model,
                "in": rec.input_tokens,
                "out": rec.output_tokens,
                "cc": rec.cache_creation_input_tokens,
                "cr": rec.cache_read_input_tokens,
            },
        )
        latest_uuid = rec.uuid
        new_entries += 1

    if latest_uuid:
        cursors[session_id] = latest_uuid
        _write_cursors(cursors_file, cursors)

    return 0


def _read_cursors(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cursors(path: Path, cursors: dict[str, str]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cursors, indent=2))
    os.replace(tmp, path)


def _safe_branch(branch: str) -> str:
    # Branch names can contain "/", which becomes a subdirectory unless we sanitize.
    return branch.replace("/", "__").replace("\\", "__")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
