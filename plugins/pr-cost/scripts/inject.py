#!/usr/bin/env python3
"""Append the cost block to the open PR body for the current branch.

Two entry modes:
- Default: look up the open PR for the current branch and inject.
- --from-hook: read PostToolUse JSON from stdin. If the executed command was
  `gh pr create` and `auto_inject_on_gh_pr_create` is true, inject. Otherwise
  exit silently.

Idempotent: any prior pr-cost block in the PR body is stripped before append.
Never breaks the user's session — errors are reported to stderr but exit 0
when invoked from a hook.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import aggregate, config, format as fmt, pricing, repo_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-hook", action="store_true",
                        help="Invoked by PostToolUse hook; read payload from stdin")
    parser.add_argument("--branch", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--pr", default=None, help="PR number (skip auto-detection)")
    args = parser.parse_args()

    cfg = config.load()

    if args.from_hook:
        payload = _read_hook_payload()
        if payload is None:
            return 0
        if not _is_gh_pr_create(payload):
            return 0
        if not cfg.get("auto_inject_on_gh_pr_create", True):
            return 0
        repo = Path(payload.get("cwd") or os.getcwd()).resolve()
        # Suppress all stderr output in hook mode to avoid surprising the user
        return _do_inject(cfg, repo, args.branch, args.pr, silent=True)

    repo = Path(args.repo).resolve() if args.repo else Path.cwd()
    return _do_inject(cfg, repo, args.branch, args.pr, silent=False)


def _do_inject(
    cfg: dict,
    repo: Path,
    branch_arg: str | None,
    pr_arg: str | None,
    silent: bool,
) -> int:
    def err(msg: str) -> None:
        if not silent:
            print(msg, file=sys.stderr)

    branch = branch_arg or _current_branch(repo)
    if not branch:
        err("Error: could not determine current branch")
        return 0 if silent else 2

    pr_number = pr_arg or _pr_number_for_branch(repo, branch)
    if not pr_number:
        err(f"No open PR found for branch '{branch}'")
        return 0 if silent else 1

    slug = repo_id.slug_for(repo)
    usage_path = config.expand(cfg["usage_dir"]) / slug / f"{_safe_branch(branch)}.jsonl"
    totals = aggregate.aggregate_file(usage_path)
    if totals.turns == 0:
        err(f"No Claude Code usage recorded for branch '{branch}'")
        return 0 if silent else 1

    price_data = pricing.load(
        config.expand(cfg["pricing_dir"]),
        cfg["pricing_url"],
        int(cfg["pricing_cache_ttl_hours"]),
    )
    block = fmt.render(totals, branch, price_data, bool(cfg["show_dollars"]))

    current_body = _gh_pr_body(repo, pr_number)
    if current_body is None:
        err(f"Failed to read PR #{pr_number} body")
        return 0 if silent else 1

    new_body = fmt.strip_block(current_body)
    if new_body:
        new_body = new_body.rstrip() + "\n\n" + block
    else:
        new_body = block

    if not _gh_pr_set_body(repo, pr_number, new_body):
        err(f"Failed to update PR #{pr_number} body")
        return 0 if silent else 1

    if not silent:
        print(f"Injected cost block into PR #{pr_number}")
    return 0


def _read_hook_payload() -> dict | None:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None


def _is_gh_pr_create(payload: dict) -> bool:
    if payload.get("tool_name") != "Bash":
        return False
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    # Match `gh pr create` but not `gh pr created` or `gh pr createsomething`
    return "gh pr create" in command and _word_followed(command, "gh pr create")


def _word_followed(s: str, prefix: str) -> bool:
    idx = s.find(prefix)
    while idx != -1:
        end = idx + len(prefix)
        if end == len(s) or not s[end].isalnum():
            return True
        idx = s.find(prefix, end)
    return False


def _current_branch(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo), capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            b = out.stdout.strip()
            return b if b and b != "HEAD" else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return None


def _pr_number_for_branch(repo: Path, branch: str) -> str | None:
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "open",
             "--json", "number", "--limit", "1"],
            cwd=str(repo), capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout or "[]")
        if not data:
            return None
        return str(data[0].get("number") or "")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def _gh_pr_body(repo: Path, pr_number: str) -> str | None:
    try:
        out = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "body", "--jq", ".body"],
            cwd=str(repo), capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        # `--jq .body` strips outer quotes; raw stdout is the body string.
        body = out.stdout
        # `gh ... --jq` appends a trailing newline; preserve internal content
        if body.endswith("\n"):
            body = body[:-1]
        return body
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _gh_pr_set_body(repo: Path, pr_number: str, body: str) -> bool:
    try:
        out = subprocess.run(
            ["gh", "pr", "edit", pr_number, "--body-file", "-"],
            cwd=str(repo), input=body, capture_output=True, text=True, timeout=15,
        )
        return out.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _safe_branch(branch: str) -> str:
    return branch.replace("/", "__").replace("\\", "__")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Hook safety: never break the user's session
        sys.exit(0)
