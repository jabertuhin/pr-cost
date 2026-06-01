"""Derive a stable, collision-free repo slug from git remote URL."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def slug_for(cwd: Path) -> str:
    """Return a slug like 'github.com-org-repo' or fall back to basename."""
    remote = _run(["git", "remote", "get-url", "origin"], cwd)
    if remote:
        return _slugify(remote)
    return _safe(cwd.name) or "unknown"


def _slugify(url: str) -> str:
    url = url.strip()
    if url.endswith(".git"):
        url = url[:-4]
    # git@github.com:org/repo  ->  github.com/org/repo
    m = re.match(r"^[\w.-]+@([\w.-]+):(.+)$", url)
    if m:
        url = f"{m.group(1)}/{m.group(2)}"
    # https://user:pw@host/path  ->  host/path
    url = re.sub(r"^[a-z]+://(?:[^@/]+@)?", "", url)
    return _safe(url)


def _safe(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9.\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    return s
