# Linters

## Purpose
Configuration files for Python code quality and static analysis tools. Centralizes linting, type checking, and refactoring rules across the dotfiles project.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `.pylintrc` | Pylint configuration for Python code style, complexity, and error detection | Disables line-length checks (delegated to ruff), configures max-nested-blocks=5, max-args=5, max-attributes=7 |
| `.sourcery.yaml` | Sourcery refactoring tool configuration | Ignores venv, node_modules, vendor, and specific heavy modules (mingpt) |
| `pyrightconfig.json` | Pyright static type checker configuration | Includes current directory, excludes build artifacts and cache directories |

## Patterns
- **Configuration-as-code**: Each tool has its own config file in the project root (symlinked from this directory during setup)
- **Tool separation of concerns**: Pylint handles style/complexity, Pyright handles type checking, Sourcery handles refactoring suggestions
- **Large exclusion lists**: All tools exclude node_modules, build artifacts, cache directories, and ML experiment outputs to improve performance

## Dependencies
- **External tools**: pylint, pyright, sourcery
- **No internal dependencies**: Configuration files only; no imports or cross-references

## Entry Points
None. These are declarative configuration files sourced by linting tools via standard config file discovery.

## Notes
- `.pylintrc` delegates line-length and unused-variable detection to ruff (faster and more accurate)
- Pyright reports missing imports (`reportMissingImports: true`)
- Sourcery configured for Python 3.7+ compatibility
