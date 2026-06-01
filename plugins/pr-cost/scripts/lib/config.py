"""Config loading/saving for ~/.claude/pr-cost/config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".claude" / "pr-cost"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "auto_inject_on_gh_pr_create": True,
    "show_dollars": True,
    "pricing_url": "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
    "pricing_cache_ttl_hours": 24,
    "usage_dir": str(CONFIG_DIR / "usage"),
    "pricing_dir": str(CONFIG_DIR / "pricing"),
    "state_dir": str(CONFIG_DIR / "state"),
}


def load() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save(DEFAULTS)
        return dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def save(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    os.replace(tmp, CONFIG_PATH)


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path))
