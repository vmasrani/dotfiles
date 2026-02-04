# vscode

## Purpose
Contains VS Code profile exports for language-specific development environments (Python, Markdown, LaTeX). Each profile is a portable JSON snapshot of extensions, settings, keybindings, and snippets.

## Key Files
| File | Role | Size |
|------|------|------|
| python.code-profile | Python development profile with 67+ extensions, Python-specific settings, debugging keybinds | 366 KB |
| markdown.code-profile | Markdown editing profile with spell check, writing tools, and markdown-optimized settings | 219 KB |
| latex.code-profile | LaTeX/academic writing profile with Python support and manuscript-focused extensions | 195 KB |

## Profile Structure
Each `.code-profile` is a JSON file containing:
- **name**: Profile identifier (e.g., "python", "markdown", "latex")
- **extensions**: Array of installed VS Code extensions with identifiers, display names, versions, and disabled status flags
- **settings**: JSON string of editor and extension configurations (indentation, fonts, language-specific rules, linting)
- **keybindings**: Custom keyboard shortcuts (JSON string with key combinations and command mappings)
- **snippets**: User-defined code snippets
- **globalState**: Global workspace state variables

## Key Extensions

### Python Profile (67+ extensions)
- **Development**: Cursor Pyright, Pylint, Ruff, Python Debugger
- **AI/Assistance**: Claude Code, ChatGPT, IntelliCode
- **Version Control**: GitLens, Git History, Git Graph
- **Data Tools**: Jupyter, Data Wrangler, Jupyter Renderers
- **Database**: SQLite Viewer, PostgreSQL, MongoDB for VS Code
- **Utilities**: Remote SSH, Path Intellisense, Better Align, File Utils

### Markdown Profile
- **Writing**: Language Tool (grammar checking), Code Spell Checker
- **Markdown Tools**: Markdown Shortcuts, Better Markdown
- **Themes**: Material Theme, Palenight Theme
- **Utilities**: Rainbow CSV, PDF Viewer, File Utils

### LaTeX Profile
- **Python Integration**: Python, Pylint, Python Debugger, Jupyter
- **Development**: Ruff, Command Runner, Git tools
- **Database**: PostgreSQL, MongoDB support
- **Utilities**: PDF Viewer, Remote SSH, File Utils

## Settings Patterns
- **Shared defaults**: Material Icon Theme, word wrap enabled, 4-space indentation, line cursor style
- **Python-specific**: Tab size 4, spaces, quick suggestions enabled, format on type disabled
- **Markdown-specific**: Word wrap on, trim trailing whitespace disabled, language tool integration
- **LaTeX-specific**: Python linting enabled, flake8 configuration, extended linting for scientific libraries

## Keybindings
Each profile customizes keybinds for workflow efficiency:
- **Navigation**: Cmd+L for sidebar toggle, Shift+Cmd+; for goto line
- **Debugging**: Alt+K (step into), Alt+J (step over), Alt+L (step out)
- **History**: Shift+Cmd+M (navigate back), Shift+Alt+Cmd+M (navigate forward)
- **Interaction**: Alt+Up/Down for command palette, Cmd+Shift+P for command access

## Dependencies
- **VS Code**: 1.90+ (estimated from extension versions)
- **External**: Material Theme family, Jupyter ecosystem, Python tooling (Pylint, Ruff, Pyright)
- **Internal**: Symlinked to `~/.config/Code/User/profiles/` during dotfiles setup

## Entry Points
These profiles are portable exports meant to be imported into VS Code via:
- Settings Sync
- Manual import via VS Code Profiles UI
- Symlink mapping (if configured in setup.sh)

## Note
Profiles are snapshots that capture workspace state at export time. Extensions require marketplace access to reinstall; settings are static configurations. The 366 KB Python profile is the largest due to 10K+ extensions and comprehensive settings for data science/ML workflows.
