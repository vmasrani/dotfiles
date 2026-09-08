# Standing dispatch preamble — environment doctrine that is NOT issue content

Paste (or reference) this ONCE per project — in `.agent-workflow/`, CLAUDE.md,
or the wave/dispatch preamble. Every line below hit 2–10 implementing sessions
identically in the 2026-08 post-mortem; none is specific to any issue.
Keep it adapted to the box/repo; delete lines that don't apply.

## Where you work
- Absolute worktree path, branch, base sha, "data symlinked / hydrated, claim posted" — stated up front.
- Anchor every command with `cd <worktree> &&`; after any side-trip into a reference repo, `cd` back before `uv`/`git`.
- Never touch the primary checkout or another task's worktree. Never edit a sibling repo; if you must to unblock, `git status`/`git diff` it before reporting done and either commit (scoped `git add <file>`) or revert — never leave it dangling.
- Step 0 in a fresh worktree: `uv sync` explicitly (a cold `uv run` blows the tool timeout).

## Heavy commands and the shared box
- Prefix with `queue`: `just ci-fast`, `just test`, `just ci-deep`, any count-matrix / index build / live-scorer / report regeneration — exact form: `queue "just ci-fast > /tmp/cifast.log 2>&1; echo exit=\$?"` (ONE quoted string; the shell splits on `;`/`>` otherwise).
- `run_in_background: true` is not `queue`. Memory, not cores, is the cliff; N sibling workers share this box.
- A queued/background task's own "exited 0" is the WRAPPER's exit, not the command's — always `rg -n 'passed|failed|error|exit=' <log>` before calling a gate green. `queue` exit 255 = dropped/cancelled.
- A SIGTERM/exit 143/OOM mid-run is not the lead killing you and not a stop signal — chunk the work and resubmit through `queue`.
- Before resubmitting anything heavy (especially after a context compaction), `queue -l` / `queue --triage` — your job may already be running.
- If the ci-fast aggregate is stuck >2 min behind someone else's job, running its sub-recipes directly is an acceptable substitute — say which you ran.
- Regenerate expensive artifacts (tens of minutes) exactly once, as the last step, at the final sha; batch content fixes first; reports name their producer sha.

## Gates, lint, types
- `ruff format` is a SEPARATE gate from `ruff check`; run both on touched files before the first heavy ci-fast (don't burn a 10-min gate on a formatting fail; don't unwind commits).
- Non-default lint rules live in `pyproject.toml [tool.ruff.lint]`.
- `ty check` gotchas: `.itertuples()` attribute access and `groupby` tuple-unpacking don't narrow — use typed NamedTuple/dataclass or `.to_dict("records")`; `scripts/*.py` are `uv run --script` entry points, load them in tests via `importlib.util.spec_from_file_location`, never `sys.path` + import.
- Only tests under the gate's collection path count (e.g. `tests/tier0/`); verify a filter selected >0 tests; compare against the stated baseline count.
- The gate is absolute: a red test outside your owned files is STOP-and-report, never "expected, ship anyway".
- Never pipe a test/build/push command into `tail`/`head` — the exit code becomes tail's. Capture to a log, end with `; echo exit=$?`.

## This box
- macOS: BSD `pgrep`/`sed`/`find` — no `pgrep -c` (use `pgrep -f … | wc -l`), no GNU flags.
- `pmap` process mode raises EOFError in this sandbox — use `prefer='threads'`.
- `rg`: `-r` is `--replace` (hook-blocked); `-n` and `-l` are mutually exclusive.
- A new package dir that shares a name with an editable-installed sibling's (`app/` next to `../other/app/`) is silently shadowed until `__init__.py` exists — create it first.
- YAML barewords `on/off/yes/no` parse as booleans — quote enum-like values in config/grid files.

## gh / git
- Any `gh issue|pr … --body` containing backticks or code fences → `--body-file`, always.
- PRs target `dev`, so `Closes #N` never auto-fires — `gh issue close -c "<summary>"` explicitly, last.
- dev PRs run only secret-scan + workflow-lint; local `ci-fast` green is the real gate — don't wait for a check that won't appear.
- Merge with `--merge` (never squash); rebase only if the repo's producer-sha/report convention allows it; behind dev → `gh pr update-branch --rebase`.
- `data/*` + `!data/README.md` when a tracked file lives inside an ignored dir (`data/` + negation does not un-ignore); worktree symlinks per-subdir accordingly.
- No `Co-Authored-By`. No push/merge unless the dispatch says so.

## Talking to the lead
- When you start a multi-minute queued job, post ONE line: what's running, ETA. Silence during a legitimate wait reads as "stuck".
- Final report ≤12 lines: sha / exact counts / conflicts / anything undone / which sibling report is affected by any discrepancy.
- If a ground rule turns out wrong or missing, say so on the EPIC issue (comment), not just in your branch.
- Don't narrow scope quietly; stop and name the blocker.

## Lead-side (for the dispatcher)
- Cross-check `git status` / `queue -l` / `pgrep` before nudging a worker about idleness or a "bare" job — two nudges in the post-mortem were stale-monitoring artifacts.
- Broadcast a cross-cutting fix to every open sibling the hour it's found, and back-port it into the epic body.
- Scope one-time operational instructions with an end condition ("kill what's queued NOW"), never as a standing policy.
- A pivot that will kill a session needs wind-down runway (commit WIP, push, handoff comment) — or a fresh short agent does it.
