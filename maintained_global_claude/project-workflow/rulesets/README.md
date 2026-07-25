# Org rulesets

Branch rules live at the **organization** level, not per repository. One
definition covers every repo in `sophiaconsulting`, including repos that do not
exist yet — which is the whole point: there is no per-repo protection step to
forget. These JSON files are the source of truth; the GitHub UI is a view of
them.

This replaced the per-repo `gh api repos/*/branches/*/protection` calls that
`project-workflow gh-setup` used to make. Those calls had to be re-run for every
new repo, and in practice never were.

## The two rulesets

**`baseline-history-protection`** — every repo (`~ALL`), on `main`/`master`/`dev`.
Blocks force-pushes and branch deletion. Nothing else. Direct pushes to `dev`
still work, which is deliberate: `dev` is the working branch and gating it on
status checks would reject the push outright (required status checks apply to
direct pushes, not only to merges).

**`agent-workflow-main-strict`** — only repos whose `agent-workflow` custom
property is `true`, on `main`. Requires a PR and a green `Deep integration
checks`. Because the property defaults to `false`, a repo is unaffected until it
is explicitly opted in — so a new repo without CI can never be born with an
unsatisfiable required check.

`required_approving_review_count` is `0` on purpose. A solo maintainer who
requires an approving review can never merge anything; the gate here is the
green check, not a second human.

`bypass_actors` is empty on purpose. Org owners would otherwise bypass the very
rules meant to catch their own accidents. There is no lockout risk: an owner can
disable a ruleset from org settings at any time, unlike classic branch
protection's `enforce_admins`.

## Applying

Creating rulesets requires the `admin:org` scope:

    gh auth refresh -h github.com -s admin:org

`gh ruleset` is read-only (`list`/`view`/`check`), so writes go through the API:

    gh api --method POST orgs/sophiaconsulting/rulesets \
        --input rulesets/baseline-history-protection.json

To update an existing ruleset, PUT to its id (find it with `gh ruleset list --org sophiaconsulting`):

    gh api --method PUT orgs/sophiaconsulting/rulesets/RULESET_ID \
        --input rulesets/baseline-history-protection.json

## The custom property

Created once per org; `project-workflow gh-setup --apply` sets it to `true` for
a repo as the final step of setup.

    gh api --method PUT orgs/sophiaconsulting/properties/schema/agent-workflow \
        -f value_type=true_false -F required=true -f default_value=false

## Verifying

Never trust a ruleset because the POST returned 201. Check what actually applies
to a branch:

    gh ruleset check main --repo sophiaconsulting/parot-web

A required status check whose context never reports makes the branch
permanently unmergeable, so confirm the context string matches a real job
`name:` in a workflow that triggers on `pull_request` into that branch.
