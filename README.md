# pr-cost

A Claude Code plugin that tracks per-branch Claude Code token spend and embeds
it as a cost block in your PR descriptions.

```
## 🤖 Claude Code Spend

| Model | Input | Output | Cache W / R | Cost |
|---|---:|---:|---:|---:|
| opus-4-7 | 12.4K | 48.2K | 1.2M / 320K | $4.21 |
| sonnet-4-6 | 3.1K | 8.0K | 220K / 0 | $0.18 |
| **Total** | **15.5K** | **56.2K** | **1.4M / 320K** | **$4.39** |

_branch `feature/x` · 27 turns across 3 sessions · pr-cost v0.1.0_
```

When only one model contributed, the Total row is omitted (it would
duplicate the single data row).

## How it works

1. A `Stop` hook fires at the end of every Claude Code turn and rolls up that
   turn's token usage into `~/.claude/pr-cost/usage/<repo-slug>/<branch>.jsonl`.
   Branch is read from the `gitBranch` field already present on every transcript
   line, so mid-session branch switches are handled correctly.
2. `/pr-cost` renders the cost block from the aggregate (no transcript re-walk)
   and prompts you to inject it into the open PR for the current branch.
3. Optional: a `PostToolUse` hook auto-injects the block whenever Claude Code
   itself runs `gh pr create`. The hook only fires for `gh pr create` invoked
   by Claude Code — if you run `gh pr create` in a separate terminal, use
   `/pr-cost` to inject after the PR is open. Toggle the auto-inject off via
   `auto_inject_on_gh_pr_create: false`. The `Stop` capture hook keeps running
   regardless; the config only gates injection.

Pricing comes from
[LiteLLM's `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json),
the same source [ccusage](https://github.com/ryoppippi/ccusage) uses. Cached
on disk for 24h with a bundled fallback snapshot for offline first runs.

## Install

From the public marketplace:
```
/plugin marketplace add jabertuhin/pr-cost
/plugin install pr-cost@pr-cost
```

Or via the CLI (equivalent, scriptable):
```
claude plugin marketplace add jabertuhin/pr-cost
claude plugin install pr-cost@pr-cost
```

For local development install (point at a checkout instead of the public repo):
```
claude plugin marketplace add /path/to/pr-cost
claude plugin install pr-cost@pr-cost
```

Requires `python3` (stdlib only — no `pip install`) and `gh` for PR injection.
Tested on macOS and Linux; Windows is untested.

## Verify, update, uninstall

```
claude plugin list                                              # confirm enabled
claude plugin marketplace update pr-cost && claude plugin update pr-cost@pr-cost
claude plugin uninstall pr-cost@pr-cost
```

## Configuration

`~/.claude/pr-cost/config.json` (auto-created on first hook fire):

```json
{
  "auto_inject_on_gh_pr_create": true,
  "show_dollars": true,
  "pricing_url": "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
  "pricing_cache_ttl_hours": 24,
  "usage_dir": "~/.claude/pr-cost/usage",
  "pricing_dir": "~/.claude/pr-cost/pricing",
  "state_dir": "~/.claude/pr-cost/state"
}
```

- `auto_inject_on_gh_pr_create` — `false` to disable the PostToolUse hook;
  the `/pr-cost` slash command still works and capture continues.
- `show_dollars` — `false` to show tokens only (no `$` column or row).

## Usage

- `/pr-cost` — print the cost block for the current branch in chat, then
  prompt to inject into the open PR.
- The PostToolUse hook auto-injects whenever Claude Code itself runs
  `gh pr create` (when enabled).

## Data on disk

```
~/.claude/pr-cost/
  config.json
  pricing/litellm.json          # 24h cache
  state/cursors.json            # per-session JSONL read cursors
  usage/<repo-slug>/<branch>.jsonl
```

Repo slug is derived from the `origin` remote URL (e.g. for
`git@github.com:acme/widgets.git` the slug is `github.com-acme-widgets`),
not from your GitHub username — that's what avoids collisions between
clones of differently-owned forks.

## Limitations

- Single-machine attribution. If two people work on the same branch from
  different machines, each machine's costs are recorded locally.
- Counts only Claude Code spend, not Codex / API / Anthropic Console usage.
- Hooks must be enabled in the same Claude Code installation that runs the
  agent — if hooks are disabled, no data is captured.

## License

MIT
