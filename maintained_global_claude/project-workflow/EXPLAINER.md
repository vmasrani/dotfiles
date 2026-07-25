# How the branch rules actually work

Written for someone who has never used branch protection, rulesets, custom
properties, required status checks, or git hooks. This explains the *mechanics*
of the system in `rulesets/` and `templates/pre-push`; `rulesets/README.md`
covers how to apply and change it.

**In one sentence:** a per-repository, imperative "go configure each repo" step
was replaced with a declarative rule engine that lives at the organization level
and selects repos by metadata, plus a local git hook guarding the one path the
server deliberately leaves open.

## Mental model

There are exactly two enforcement points, at different moments in the life of a
change:

```
your machine                                    github's servers
────────────                                    ────────────────
edit → commit → [ pre-push hook ] → push ────→ [ ruleset ] → branch updated
                  local gate                     server gate
```

`main` is guarded on the server. `dev` is guarded only on your machine. That
asymmetry is forced by a technical constraint, not chosen for taste — see §4.

## 1. What a ruleset is, and where it lives

GitHub's first-generation feature was **branch protection rules**: configured
inside one repository's settings, one rule per branch-name pattern. **Rulesets**
are the second-generation replacement. A ruleset has four parts:

```
{
  conditions:    which branches, in which repos, this applies to   ← the matcher
  rules:         what is then required or forbidden                ← the predicate
  enforcement:   active | disabled
  bypass_actors: who is exempt
}
```

The critical property: **a ruleset is server-side state living in organization
settings.** It is not a file, not in git history, and invisible from a clone.
This is why "no protection anywhere" was undetectable by reading the repos and
only surfaced by querying the API — nothing in a checkout can tell you.

## 2. Why organization-level beats per-repository

```
BEFORE (what gh-setup used to do)
  setup-project ──→ PUT /repos/parot-core/branches/main/protection
                ──→ PUT /repos/parot-web/branches/main/protection
                ──→ PUT /repos/parot-radar/branches/main/protection
  repo created tomorrow ──→ nothing. someone must remember to re-run it.

AFTER
  one ruleset ──matches at evaluation time──→ core, web, radar,
                                              and the repo created tomorrow
```

The per-repo form is O(repos) imperative calls with no mechanism at all for
repos that don't exist yet. The org form states a condition once; membership is
recomputed on every push or merge. The original failure was the predictable
consequence: the step existed in the code and had been run zero times across
four repos.

## 3. Custom properties — how a rule finds its repos

A **custom property** is a typed key/value the org defines once and attaches to
repositories. Metadata beside the repo record; not a file, not visible to a
clone.

We define one: `agent-workflow`, type `true_false`, default `false`. Its only
job is to be what a ruleset's `conditions` matches on:

```
conditions.repository_property.include = [{ agent-workflow: true }]
                    │
     ┌──────────────┴───────────────┐
  parot-core   parot-web   parot-radar        ← rule applies
  every other repo (false)                    ← rule does not exist for them
```

Name patterns would also work, but they bind policy to a naming convention that
nothing enforces. A property is a label: set membership decided by data set
deliberately.

**The `false` default is doing real safety work.** The strict rule requires a
status check named `Deep integration checks`. Applied to a repo with no such
workflow, that is a requirement nothing can satisfy — a branch where no pull
request can ever merge, permanently. Defaulting to `false` means no repo is born
into a rule it cannot satisfy. This is the sharpest edge in the system; always
confirm the context string matches a real job `name:` before opting a repo in.

## 4. Required status checks, and why `dev` has none

A **status check** is a named result an external system posts against a **commit
SHA**. GitHub Actions posts one per job, named by that job's `name:` field. So
`Deep integration checks` is not a concept — it is a string that must match a
job name character-for-character.

The check attaches to a *commit*, not to a branch or a pull request. Watch what
that means for a direct push:

```
git push origin dev
   server: the tip of dev would become commit abc123.
           rule says abc123 must have "Deep integration checks" passing.
           what checks does abc123 have?
   → none. it was created four seconds ago. nothing has run against it.
   → REJECTED
```

CI runs *because* a commit reached the server, but the commit cannot reach the
server until CI has run. The pull-request flow dissolves this: the commit lives
on a feature branch carrying no rules, CI runs there freely, and the requirement
is evaluated only at *merge* time. A direct-push branch has no such staging
area.

So requiring status checks on `dev` is not "a stricter dev" — it is exactly
equivalent to **banning direct pushes to dev**. Since `dev` is meant to stay
directly pushable, an empty required-check list is the only configuration that
means what we want.

This is also the bug in the code this replaced: the old `gh_setup` set required
checks on `dev`, so running it as written would have started rejecting
`git push origin dev`.

## 5. The pre-push hook — what actually guards `dev`

Git executes scripts at defined lifecycle points. **`pre-push`** runs after
`git push` is invoked, before anything crosses the network. A non-zero exit
aborts the push.

The wrinkle is where hooks live. By default that is `.git/hooks/`, which is
**not repository content** — not committed, not cloned, not synced. That is
deliberate (cloning a repo must never execute code its author chose for you),
but it means a hook cannot be shipped by committing it.

The resolution is `core.hooksPath`, a git config setting redirecting the hook
directory:

```
.githooks/pre-push          ← committed. travels with the repo. shows up in a diff.
      ▲
      │  core.hooksPath = .githooks
      │  ← local config. per clone, per machine. NOT committed.
   git push
```

Two halves must both be present: **the file** (shipped in git) and **the
arming** (local config). `just install-hooks` is the arming — one `git config`
line, run once per clone per machine.

That split is why `project-workflow check` *fails* when `core.hooksPath` is
unset rather than merely noting it. A `.githooks/pre-push` in a repo git is not
pointed at looks completely installed and gates nothing: the repo appears
guarded while every push sails through. Same "skipped and passed are observably
identical" failure as a red CI run nobody reads, one layer down.

The hook runs `just pre-push` → format check plus lint, **never tests**. The
reasoning is behavioral, not technical: a gate slow enough to irritate gets
`--no-verify`'d out of habit, and a habitually bypassed gate is worse than none,
because you believe you are covered. Lint is seconds.

## 6. End to end

```
DIRECT PUSH TO DEV  — allowed, locally gated
  commit → git push
      ├─ pre-push hook runs `just pre-push` (fmt + lint)
      │      └─ non-zero → push aborted, nothing left your machine
      └─ pass → network → server evaluates rulesets against refs/heads/dev
             baseline-history-protection: force-push? deletion? → neither → OK
             (dev has no required checks, by design)            → branch updated
             Deep CI then runs on the push — informational, gates nothing

PROMOTION DEV → MAIN  — server gated
  open PR dev → main
      └─ agent-deep.yml fires on pull_request: branches: [main]
             └─ posts status "Deep integration checks" on the PR head commit
  merge
      └─ agent-workflow-main-strict evaluates:
            is this repo agent-workflow = true?          yes
            pull_request rule — is there a PR?           yes
            required check "Deep integration checks"?    red   → merge blocked
                                                        green → merged
```

Underneath both, on every repo including future ones: force-push and branch
deletion blocked on `main`, `master`, and `dev`.

## Design notes

**Rulesets are a declarative constraint system evaluated at ref-update time.**
`conditions` is the matcher, `rules` is the predicate, and the rule's extension
is recomputed on every evaluation rather than materialized once at setup. That
is the entire reason future repos are covered for free, and precisely what the
imperative `PUT .../protection` form could not express.

**`bypass_actors: []` generalizes an old boolean.** First-generation branch
protection had `enforce_admins: true|false`; rulesets replace it with a list of
exempt actors. It is empty here because the org owner is the primary pusher —
self-exemption would make every rule vacuous for exactly the person whose
accidents they exist to catch. No lockout risk: disabling a ruleset is a setting
the owner controls at any time, unlike `enforce_admins`, which was a real trap.

**`default: false` fails closed in the useful direction.** The rule's extension
starts empty, so a misconfiguration cannot brick a repo's merge button — it can
only fail to protect one, which is visible and recoverable. The inverse default
would let a single mistake render `main` unmergeable across the whole org.

**One invariant, three layers.** A check that cannot run must be visibly absent,
never silently green. The `core.hooksPath` assertion in `check`, the
`gh ruleset check` call at the end of `gh-setup`, and the loud-failing generated
`pre-push` recipe when no fmt/lint recipe exists are the same rule enforced at
three different levels of the stack.
