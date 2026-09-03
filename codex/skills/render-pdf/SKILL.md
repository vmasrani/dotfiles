---
name: render-pdf
description: Render a markdown file to a polished, modern PDF using pandoc + eisvogel + xelatex. Use when the user wants to convert markdown to PDF, generate a report PDF, make a polished document, or says "render pdf", "make a pdf", "markdown to pdf".
user_invocable: true
---

# Render Polished PDF from Markdown

Convert a markdown file into a clean, modern, professional PDF using the eisvogel pandoc template. Produces tech-report style output (sans-serif fonts, colored title page, callout boxes) — not academic LaTeX.

## Prerequisites

Before starting, verify these are installed:

```bash
pandoc --version && xelatex --version && echo "OK"
```

If missing:
- **pandoc**: `brew install pandoc`
- **xelatex**: `brew install --cask mactex-no-gui` (or `basictex`)
- **eisvogel template**: `pandoc-eisvogel` — check with `pandoc --template eisvogel -o /dev/null /dev/null 2>&1`. If missing: download from https://github.com/Wandmalfarbe/pandoc-latex-template/releases and place in `~/.pandoc/templates/eisvogel.latex`

## Assets

This skill bundles two files in its `assets/` directory:

| File | Purpose |
|------|---------|
| `assets/header.tex` | LaTeX preamble: callout box styles (tcolorbox), image centering, code block fixes |
| `assets/callouts.lua` | Lua filter: converts `::: warningbox` / `::: notebox` / `::: dangerbox` / `::: tipbox` fenced divs to colored LaTeX boxes |

The assets directory is at: `~/.codex/skills/render-pdf/assets/`

## Step 1 — Identify the input

The user provides a markdown file path as the argument (e.g., `/render-pdf docs/report.md`).

- If no argument given, look for a single `.md` file in the current directory
- If multiple `.md` files exist, ask the user which one

Read the markdown file to understand its structure.

## Step 2 — Ensure YAML frontmatter

The markdown file needs eisvogel-compatible YAML frontmatter. If the file already has frontmatter, check that it includes eisvogel keys. If it has no frontmatter or is missing key fields, **add or merge** this default frontmatter block:

```yaml
---
title: "<infer from filename or first heading>"
subtitle: ""
date: "<today's date>"
titlepage: true
titlepage-color: "1a1a2e"
titlepage-text-color: "FFFFFF"
titlepage-rule-color: "3b82f6"
titlepage-rule-height: 2
toc: true
toc-depth: 3
toc-own-page: false
colorlinks: true
linkcolor: "3b82f6"
urlcolor: "3b82f6"
mainfont: "Helvetica Neue"
sansfont: "Helvetica Neue"
monofont: "Menlo"
geometry: "left=1in,right=1in,top=1in,bottom=1.4in,footskip=50pt"
numbersections: false
book: false
block-headings: true
disable-header-and-footer: true
---
```

**Rules for frontmatter:**
- Preserve any existing frontmatter fields the user has set
- Only add missing fields from the defaults above
- Infer `title` from the filename or first `#` heading if not set
- Set `date` to today's date if not set
- **Never use Unicode arrows (-->) or special characters** in frontmatter — Helvetica Neue doesn't cover them. Use ASCII alternatives.
- Ask the user if they want to customize title page colors or other settings

## Step 3 — Pre-process wide tables

Markdown tables with 4+ columns or long backtick-wrapped content (e.g., function names) frequently overflow in PDF, causing columns to merge and become unreadable. **Proactively fix these before building.**

**Detection:** Scan for markdown tables. A table is likely too wide if:
- It has 4+ columns AND any cell contains backtick-wrapped text longer than ~25 characters
- It has 5+ columns regardless of content
- Any cell contains long text with no natural break points

**Fixes (in order of preference):**
1. **Merge columns** — combine related columns (e.g., merge "Stage" and "Function" into a single column like `Stage (function_name)`)
2. **Drop low-value columns** — remove columns that are redundant or whose content can be inferred
3. **Shorten content** — abbreviate long cell text, remove redundant prefixes, use shorter aliases

**Important:** These are cosmetic changes to the render copy only. The original file is never modified.

## Step 4 — Add page breaks (if needed)

For documents with multiple top-level `#` sections, add `\newpage{}` on a blank line before each `#` heading (except the first one) so each major section starts on a fresh page.

**Do NOT add page breaks before `##` or lower-level headings.**

## Step 5 — Build the PDF

Run:

```bash
SKILL_ASSETS="$HOME/.codex/skills/render-pdf/assets"

pandoc "<input.md>" \
  --template eisvogel \
  -H "$SKILL_ASSETS/header.tex" \
  --lua-filter="$SKILL_ASSETS/callouts.lua" \
  -o "<output.pdf>" \
  --toc --toc-depth=3 \
  --pdf-engine=xelatex
```

**Output file naming:**
- Default: same name as input with `.pdf` extension, in the same directory
- If user specifies `-o <path>`, use that
- Example: `docs/report.md` --> `docs/report.pdf`

## Step 6 — Visual inspection loop

After building, convert to PNG and inspect:

```bash
magick -density 150 "<output.pdf>" -quality 90 /tmp/render_pdf_page_%d.png
```

Read at least the first 3 pages and the last page as PNG images. Check for:

1. **Title page** renders correctly with colored background
2. **Table of contents** is present and formatted
3. **Page breaks** — each `#` section starts on a new page
4. **Code blocks** have grey background, no overflow
5. **Tables** render within margins, no clipping
6. **Callout boxes** (if any) render with colored borders
7. **No LaTeX errors** — no missing characters, no overflow warnings
8. **Images** (if any) are centered and sized correctly

**If issues found:** fix and rebuild. Common fixes:
- Unicode characters not in font --> replace with ASCII
- Table too wide --> shorten column content
- Code block overflow --> use shorter lines or add fvextra wrapping (already in header.tex)
- Missing `\newpage{}` --> add before the relevant `#` heading

Repeat the build-inspect loop until the output looks clean.

## Step 7 — Report to user

Tell the user:
- Output file path
- Page count
- Any modifications made to the markdown (frontmatter additions, page breaks)
- Any issues found and fixed during inspection

## Callout Box Syntax

The user can use these fenced div callouts in their markdown:

```markdown
::: warningbox
This is a warning message.
:::

::: notebox
This is an informational note.
:::

::: dangerbox
This is a danger/critical alert.
:::

::: tipbox
This is a helpful tip.
:::
```

These render as colored boxes in the PDF (amber for warning, blue for note, red for danger, green for tip).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Missing character: U+XXXX` | Replace the character with ASCII equivalent |
| `Command \pandocbounded undefined` | Already handled by header.tex conditional |
| `Command \chead already defined` | Don't add `\usepackage{fancyhdr}` — eisvogel loads it |
| `\undefinedpagestyle` | Don't use `\pagestyle{fancy}` — eisvogel uses KOMA-Script styles |
| `documentclass` errors | Never set `documentclass:` in frontmatter with eisvogel — use `book: false` instead |
| Table numbering counter error | Already handled by `\newcounter{none}` in header.tex |
| No eisvogel template | Install from GitHub releases into `~/.pandoc/templates/eisvogel.latex` |
| Duplicate page numbers (e.g., "8  8") | Do NOT use `footer-center: "\\thepage"` — it conflicts with eisvogel's KOMA-Script numbering. Use `disable-header-and-footer: true` instead |
| Table columns merging / overlapping | Pre-process in Step 3: reduce to 3 columns max, merge related columns, shorten backtick content. header.tex uses `\small` in longtable to help |
