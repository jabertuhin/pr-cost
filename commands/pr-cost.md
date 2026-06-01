---
description: Show Claude Code token spend for the current branch and optionally inject into the open PR
allowed-tools: Bash(python3:*), Bash(gh pr view:*), Bash(gh pr list:*), Bash(git rev-parse:*), Bash(git remote:*)
---

Run the cost report for the current branch, then ask whether to inject the result into the open PR.

## Steps

1. Run the report and show the output to the user verbatim:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py"
   ```

2. Detect whether there is an open PR for the current branch:
   ```
   gh pr list --head "$(git rev-parse --abbrev-ref HEAD)" --json number,url --limit 1
   ```

3. If a PR exists, ask the user (a single yes/no question): "Inject this cost block into PR #N? (yes/no)". Wait for their answer.

4. If the user answers yes, run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inject.py"
   ```
   Otherwise stop. Do not inject without explicit confirmation.

5. If no open PR exists for the branch, tell the user and stop — do not attempt to create one.
