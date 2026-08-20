---
name: make-release-readme
description: Generate a polished, release-quality README.md with comprehensive Playwright screenshots of every feature in a web app. Use this skill whenever the user wants a README, wants to document their app with screenshots, says "make a readme", "release readme", "document this project", "screenshot the app for a readme", or wants to prepare a repo for public release. Also use when the user asks for project documentation with visuals, or wants to showcase their app's features.
---

# Make Release README

Generate a professional README.md with embedded screenshots for any web application. Read the codebase to understand features, use Playwright MCP to screenshot everything, and produce a release-ready document.

## Phase 1 — Codebase Analysis

Understand the project before taking any screenshots. Read these files (whichever exist):

- **Identity**: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, or top-level config — extract app name, description, version
- **Tech stack**: Dependencies, frameworks, languages in use
- **Setup**: `justfile`, `Makefile`, `docker-compose.yml`, `package.json` scripts — how to install and run
- **Routes/pages**: Scan for route definitions, page components, navigation structures to enumerate features
- **Existing docs**: Current `README.md`, `CHANGELOG.md`, `LICENSE`

Build a **feature inventory** — a bulleted list of every user-facing feature discovered. Present it to the user and ask them to confirm, add, or remove items before proceeding. This prevents wasting time screenshotting irrelevant pages.

## Phase 2 — Get App URL

Ask the user: "What URL is the app running at?" (e.g., `http://localhost:3000`).

If the app isn't running yet, offer to start it using the setup commands discovered in Phase 1. Wait until the app is confirmed running before proceeding.

## Phase 3 — Screenshot Campaign

The goal is **quantity over curation** — take lots of screenshots so the user can cherry-pick favorites later. Create a `screenshots/` directory in the project root.

### Naming convention

```
screenshots/{feature}-{state}-{viewport}.png
```

- **feature**: kebab-case name from the feature inventory (e.g., `dashboard`, `settings-panel`, `login-form`)
- **state**: UI state captured — `default`, `empty`, `filled`, `hover`, `modal-open`, `expanded`, `dark`, `error`, `success`, `loading`, `step1`/`step2`/etc.
- **viewport**: `desktop`, `tablet`, `mobile`

### Viewport sizes

Use `browser_resize` before each viewport set:

| Name    | Width | Height |
|---------|-------|--------|
| desktop | 1280  | 800    |
| tablet  | 768   | 1024   |
| mobile  | 375   | 812    |

Major features get all three viewports. Minor features get desktop only.

### Screenshot workflow

For each feature in the inventory:

1. **Navigate** — `browser_navigate` to the feature's URL/route
2. **Snapshot** — `browser_snapshot` to get the accessibility tree and element refs
3. **Default state** — `browser_take_screenshot` with `filename: "screenshots/{feature}-default-desktop.png"`. Use `fullPage: true` for scrollable pages
4. **Interactive states** — work through these as applicable:
   - **Empty state**: If the feature displays data, find and screenshot the zero-data view
   - **Filled state**: Use `browser_fill_form` with realistic sample data, then screenshot
   - **Hover states**: `browser_hover` on key interactive elements (buttons, cards, nav items) to reveal tooltips or dropdowns, then screenshot
   - **Modal/overlay**: `browser_click` on buttons that open modals, drawers, or popovers, then screenshot
   - **Dark mode**: If a theme toggle exists, click it and re-capture
   - **Error states**: Submit invalid data to capture validation UI
   - **Success states**: Complete a flow to capture confirmations
5. **Responsive** — `browser_resize` to tablet and mobile, re-take the default screenshot at each size
6. **Element details** — For standout UI components (charts, cards, widgets), use element-specific screenshots with `ref` and `element` params. Save as `screenshots/{component}-detail-desktop.png`

### Hero screenshot

The hero is the first image anyone sees — take extra care:
- Desktop viewport, realistic data populated on screen
- `fullPage: false` for a clean viewport-sized crop
- Save as `screenshots/hero-desktop.png`
- If dark mode exists, also save `screenshots/hero-dark-desktop.png` (dark screenshots often look better on GitHub)

### Screenshot sequences

For multi-step interactions (wizards, onboarding, drag-and-drop), capture each step:
```
screenshots/onboarding-step1-desktop.png
screenshots/onboarding-step2-desktop.png
screenshots/onboarding-step3-desktop.png
```

These can be combined into GIFs in Phase 4.

## Phase 4 — GIF Creation (optional)

For screenshot sequences captured in Phase 3, offer to combine them into animated GIFs using the bundled script:

```bash
uv run {skill-directory}/scripts/make_gif.py \
  screenshots/onboarding-step1-desktop.png \
  screenshots/onboarding-step2-desktop.png \
  screenshots/onboarding-step3-desktop.png \
  --output screenshots/onboarding-flow.gif \
  --duration 1500
```

The `{skill-directory}` is the directory containing this SKILL.md file. The `--duration` flag controls milliseconds per frame (default 1500ms).

Only create GIFs if there are screenshot sequences — skip this phase otherwise.

## Phase 5 — Screenshot Review

Present a summary to the user:
- Total screenshot count
- Screenshots grouped by feature (list the filenames)
- Recommended subset for the README (typically 6-10 images: 1 hero + 1-2 per major feature)

Ask the user to review the `screenshots/` directory and indicate preferences. If they want to skip review, auto-select: prefer desktop viewport, default or populated states, and always include the hero.

## Phase 6 — Generate README.md

Write `README.md` in the project root using this structure. Adapt sections based on what's relevant — not every project needs every section.

```markdown
# {App Name}

{One-line description: what it does and who it's for.}

![{App Name} screenshot](screenshots/hero-desktop.png)

## Features

### {Feature Name}
{2-3 sentences: what this feature does and why it matters.}

![{Feature Name}](screenshots/{feature}-{best-state}-desktop.png)

<!-- Repeat for each major feature. 1-2 screenshots per feature. -->

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | {e.g., React, TypeScript, Tailwind CSS} |
| Backend | {e.g., FastAPI, Python 3.12} |
| Database | {e.g., PostgreSQL, SQLite} |

## Getting Started

### Prerequisites

- {runtime version}
- {package manager}
- {database, if applicable}

### Installation

\```bash
git clone {repo-url}
cd {project-name}
{install command}
{env setup if needed}
\```

### Running

\```bash
{start command}
\```

Open http://localhost:{port} in your browser.

## Project Structure

\```
{abbreviated tree, 2-3 levels deep, omit node_modules/__pycache__/.git}
\```

## Code Highlights

{1-2 paragraphs about interesting architectural decisions, patterns, or
algorithms. Reference specific files when relevant.}

## Responsive Design

<!-- Only include if responsive screenshots were taken -->

<p align="center">
  <img src="screenshots/{feature}-default-desktop.png" width="60%" alt="{feature} desktop view" />
  <img src="screenshots/{feature}-default-mobile.png" width="20%" alt="{feature} mobile view" />
</p>

## License

{From existing LICENSE file, or "MIT" as default}
```

### README guidelines

- **Relative paths** for all screenshot references
- **Alt text** on every image for accessibility
- **Max 10-12 images** inline in the README. If more are worth showing, add a collapsed gallery:

```markdown
<details>
<summary>More screenshots</summary>

![Screenshot 1](screenshots/extra-1.png)
![Screenshot 2](screenshots/extra-2.png)

</details>
```

- If animated GIFs were generated, embed them in the relevant feature section
- Prefer the dark mode hero if one exists — it renders better on GitHub's dark theme
- Include code blocks with syntax highlighting for setup commands
- Keep descriptions concise — the screenshots do the heavy lifting

## Phase 7 — Final Review

Present the generated README to the user. Ask:
1. Any features missing or mischaracterized?
2. Want to swap any screenshots for different ones from the `screenshots/` directory?
3. Any sections to add, remove, or reorder?

Make requested edits and confirm the final version.
