"""Render the markdown cost block."""
from __future__ import annotations

from .aggregate import BranchTotals
from .pricing import cost_for

BLOCK_MARKER = "## 🤖 Claude Code Spend"
PLUGIN_VERSION = "0.1.0"


def render(
    totals: BranchTotals,
    branch: str,
    pricing: dict,
    show_dollars: bool,
) -> str:
    if totals.turns == 0:
        return f"{BLOCK_MARKER}\n\n_No Claude Code activity recorded for branch `{branch}`._\n"

    rows = []
    grand_in = grand_out = grand_cw = grand_cr = 0
    grand_cost = 0.0
    any_unpriced = False

    for model in sorted(totals.by_model):
        m = totals.by_model[model]
        grand_in += m.input
        grand_out += m.output
        grand_cw += m.cache_write
        grand_cr += m.cache_read
        cost = cost_for(pricing, model, m.input, m.output, m.cache_write, m.cache_read)
        if cost is None:
            any_unpriced = True
            cost_cell = "—"
        else:
            grand_cost += cost
            cost_cell = f"${cost:.2f}"
        rows.append(
            f"| {_short_model(model)} | {_fmt(m.input)} | {_fmt(m.output)} | "
            f"{_fmt(m.cache_write)} / {_fmt(m.cache_read)} | {cost_cell} |"
        )

    cols = ["Model", "Input", "Output", "Cache W / R"]
    if show_dollars:
        cols.append("Cost")
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"

    if not show_dollars:
        rows = [_drop_last_col(r) for r in rows]
        total_row = (
            f"| **Total** | **{_fmt(grand_in)}** | **{_fmt(grand_out)}** | "
            f"**{_fmt(grand_cw)} / {_fmt(grand_cr)}** |"
        )
    else:
        total_cost_cell = f"**${grand_cost:.2f}**" if not any_unpriced else f"**~${grand_cost:.2f}**"
        total_row = (
            f"| **Total** | **{_fmt(grand_in)}** | **{_fmt(grand_out)}** | "
            f"**{_fmt(grand_cw)} / {_fmt(grand_cr)}** | {total_cost_cell} |"
        )

    sessions = len(totals.sessions)
    footer = (
        f"_branch `{branch}` · {totals.turns} turn{'s' if totals.turns != 1 else ''} "
        f"across {sessions} session{'s' if sessions != 1 else ''} "
        f"· pr-cost v{PLUGIN_VERSION}_"
    )

    body = "\n".join([BLOCK_MARKER, "", header, sep, *rows, total_row, "", footer, ""])
    return body


def _short_model(name: str) -> str:
    n = name.split("/")[-1]
    if n.startswith("claude-"):
        n = n[len("claude-"):]
    return n


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _drop_last_col(row: str) -> str:
    parts = row.rstrip().rstrip("|").split("|")
    return "|".join(parts[:-1]) + "|"


def strip_block(body: str) -> str:
    """Remove any prior pr-cost block so re-injection is idempotent."""
    if BLOCK_MARKER not in body:
        return body.rstrip()
    head, _, tail = body.partition(BLOCK_MARKER)
    # Drop everything from BLOCK_MARKER to the end of its footer line (the line
    # starting with `_branch ` and ending with the closing `_`). Be lenient.
    lines = tail.splitlines()
    end_idx = None
    for i, line in enumerate(lines):
        if line.startswith("_branch ") and line.rstrip().endswith("_"):
            end_idx = i
            break
    if end_idx is None:
        return head.rstrip()
    remainder = "\n".join(lines[end_idx + 1 :])
    return (head.rstrip() + "\n\n" + remainder.lstrip()).rstrip()
