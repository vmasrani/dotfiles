# Agent tools (kit-managed)

Scripts vendored by the workflow kit into `.agent-workflow/tools/`. They are
managed files: `project-workflow sync-policy` byte-compares them against the
kit and opens a `chore/policy-sync` PR on drift. Fix a bug here, in the kit,
and every kitted repo gets it — that is the entire reason they live here
rather than being re-derived per project.

To keep a deliberate local divergence, put the kit's ownership marker in a
comment in the repo's copy — the exact string is documented in
`project-workflow/README.md`. Sync then leaves that file alone, permanently,
until the marker is removed.

(The marker is not spelled out here on purpose: a managed file that quotes it
opts ITSELF out of syncing, and would silently stop receiving kit updates in
every repo that vendored it.)

## Scripts

- `hydrate-worktree.sh` — provision a fresh worktree with the gitignored
  artifacts its test suite guards on, so the suite runs the same set of tests
  in every worktree. Driven by a project-owned `.agent-workflow/hydrate.manifest`
  (see the script header for the format). **Fails loud** when a listed artifact
  is absent: a half-hydrated worktree silently runs a subset of the suite and
  still reports green, which is the same defect one level down.

  A project with no manifest gets a plain "provisions nothing, doing nothing"
  and exit 0.
