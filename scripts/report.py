#!/usr/bin/env python3
"""Render the markdown cost block for a branch."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import aggregate, config, format as fmt, pricing, repo_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Claude Code cost block for a branch")
    parser.add_argument("--branch", default=None, help="Branch name (default: current HEAD)")
    parser.add_argument("--repo", default=None, help="Repo path (default: cwd)")
    parser.add_argument("--quiet-if-empty", action="store_true",
                        help="Print nothing if no usage recorded")
    args = parser.parse_args()

    repo = Path(args.repo).resolve() if args.repo else Path.cwd()
    branch = args.branch or _current_branch(repo)
    if not branch:
        print("Error: could not determine current branch", file=sys.stderr)
        return 2

    cfg = config.load()
    slug = repo_id.slug_for(repo)
    usage_path = config.expand(cfg["usage_dir"]) / slug / f"{_safe_branch(branch)}.jsonl"

    totals = aggregate.aggregate_file(usage_path)
    if args.quiet_if_empty and totals.turns == 0:
        return 0

    price_data = pricing.load(
        config.expand(cfg["pricing_dir"]),
        cfg["pricing_url"],
        int(cfg["pricing_cache_ttl_hours"]),
    )

    block = fmt.render(totals, branch, price_data, bool(cfg["show_dollars"]))
    sys.stdout.write(block)
    if not block.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _current_branch(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            b = out.stdout.strip()
            return b if b and b != "HEAD" else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return None


def _safe_branch(branch: str) -> str:
    return branch.replace("/", "__").replace("\\", "__")


if __name__ == "__main__":
    sys.exit(main())
