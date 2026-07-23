# Agent workflow

Private reusable GitHub Actions workflows for Claude Code and Codex-managed
projects. This repository is published only by `project-workflow publish`, which
uses `gh repo create --private` and verifies the resulting visibility.

Consumers call an immutable tag, for example:

```yaml
uses: sophiaconsulting/agent-workflow/.github/workflows/agent-fast.yml@v1
```

The release tag is the compatibility boundary for all consuming projects.

The fast workflow uses Gitleaks Action v2. Consumers owned by an organization
must provide its required `GITLEAKS_LICENSE` as an Actions secret.
