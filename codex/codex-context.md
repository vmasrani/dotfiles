# codex

## Purpose
Configuration directory for Codex AI integration. Contains project mappings and MCP server configurations for enhanced development workflows.

## Key Files
| File | Role | Notable Content |
|------|------|-----------------|
| config.toml | Codex configuration | Model selection, project trust levels, MCP server setup |

## Configuration Details

### Model
- **gpt-5-codex**: Primary LLM model for Codex

### Projects
Trusted projects with Codex integration:
- `/Users/vmasrani/dev/concordance`
- `/Users/vmasrani/dev/git_repos_to_maintain/machine_learning_helpers`
- `/Users/vmasrani/dev/projects/animagic/webtools/project-template`
- `/Users/vmasrani/dev/projects/animagic/webtools/reflex-app`

### MCP Servers
- **context7**: Upstash context7 MCP server via npx with API key authentication

## Dependencies
- **External**: npx (Node.js), Upstash context7 MCP
- **Internal**: References external projects for development context
