"""Fetch + cache LiteLLM pricing JSON; fall back to bundled snapshot."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

FALLBACK_PATH = Path(__file__).with_name("pricing_fallback.json")


def load(cache_dir: Path, url: str, ttl_hours: int) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "litellm.json"
    if _is_fresh(cache_file, ttl_hours):
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    fetched = _fetch(url)
    if fetched is not None:
        try:
            cache_file.write_text(json.dumps(fetched))
        except OSError:
            pass
        return fetched
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    try:
        return json.loads(FALLBACK_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def cost_for(
    pricing: dict[str, Any],
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float | None:
    entry = _resolve(pricing, model)
    if entry is None:
        return None
    inp = float(entry.get("input_cost_per_token") or 0)
    outp = float(entry.get("output_cost_per_token") or 0)
    cw = float(entry.get("cache_creation_input_token_cost") or 0)
    cr = float(entry.get("cache_read_input_token_cost") or 0)
    return (
        input_tokens * inp
        + output_tokens * outp
        + cache_write_tokens * cw
        + cache_read_tokens * cr
    )


def _resolve(pricing: dict[str, Any], model: str) -> dict[str, Any] | None:
    if not model:
        return None
    if model in pricing:
        return pricing[model]
    # Try anthropic/<model>
    if f"anthropic/{model}" in pricing:
        return pricing[f"anthropic/{model}"]
    # Try without provider prefix
    if "/" in model and model.split("/", 1)[1] in pricing:
        return pricing[model.split("/", 1)[1]]
    # Fuzzy: longest prefix match
    candidates = [k for k in pricing if isinstance(pricing[k], dict) and model.startswith(k)]
    if candidates:
        candidates.sort(key=len, reverse=True)
        return pricing[candidates[0]]
    return None


def _is_fresh(path: Path, ttl_hours: int) -> bool:
    if not path.exists():
        return False
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age < ttl_hours * 3600


def _fetch(url: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pr-cost"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None
