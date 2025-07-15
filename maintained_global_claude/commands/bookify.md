# Bookify Command Instructions

## Purpose
Convert a directory of OCR-generated markdown files (up to 1000 pages) into a structured markdown book with bidirectional navigation and cross-references. **CRITICAL: Preserve all original text content exactly as written - do not summarize, paraphrase, or alter the meaning of any text.**

## Input
Directory containing individual markdown files from OCR processing (one file per page).

## Core Principles
1. **NEVER alter, summarize, or paraphrase the original text content**
2. **ONLY remove**: OCR artifacts, extra whitespace, page numbers, headers/footers
3. **ONLY fix**: broken sentences that span across page boundaries
4. **PRESERVE**: All meaningful content, formatting, and author's original words

## Process Overview

### Phase 1: Content Analysis & Structure Planning
1. **Read all markdown files** in the directory
2. **Analyze content structure** to identify:
   - Natural chapter/section breaks (look for title pages, clear topic shifts)
   - Headers and titles that indicate new sections
   - Content that flows across multiple files (mid-sentence breaks)
   - OCR artifacts to remove (page numbers, running headers/footers, scan artifacts)
3. **Create merge plan** specifying:
   - Exact list of files to merge into each chapter/section
   - Target filename: `03-01_title.md` (chapter 3, section 1)
   - Title extraction strategy for each merged section
   - **No text modification beyond artifact removal**

### Phase 2: Script Generation for Merging
**Instead of manually merging files, generate a script that:**
1. **Creates a merge script** (bash, Python, or similar) that:
   - Takes the list of files to merge for each section
   - Concatenates files in correct order
   - Removes only OCR artifacts (page numbers, headers, footers)
   - Fixes sentence breaks at page boundaries
   - Preserves all other content exactly
   - Outputs properly named chapter files
2. **Validates the script** before execution
3. **Saves the script** for reproducibility and review

### Phase 3: Navigation & Cross-Reference Planning
1. **Design navigation structure** with bidirectional linking
2. **Identify cross-reference opportunities** (without altering text)
3. **Plan table of contents** structure
4. **Create publishing plan** specifying:
   - Navigation headers/footers for each chapter
   - Cross-reference insertion points (as footnotes or links)
   - Index file structure

### Phase 4: Save Plans & Scripts
- Save merge script in `.bookify/merge_chapters.py` (or `.sh`)
- Save navigation plan in `.bookify/navigation_plan.json`
- Save file mapping in `.bookify/file_mapping.json`
- Document the process in `CLAUDE.md`

### Phase 5: Execute Plans
#### Merge Execution:
- **Run the generated merge script** to:
  - Combine files according to the plan
  - Remove ONLY OCR artifacts and whitespace
  - Fix broken sentences at page boundaries
  - Create properly named chapter files
  - **Preserve all original text content**

#### Navigation Execution:
- **Add navigation elements** to each chapter:
  ```markdown
  ---
  ← [Previous: Chapter Name](prev-file.md) | [Table of Contents](../index.md) | [Next: Chapter Name →](next-file.md)
  ---
  ```
- **Insert cross-references** as unobtrusive links or footnotes
- **Create index.md** with full table of contents
- **Organize files** into proper directory structure

## Output Structure
```
book-directory/
├── index.md                    # Table of contents
├── chapters/                   # All chapter files
│   ├── 01-01_introduction.md
│   ├── 01-02_overview.md
│   ├── 02-01_main_topic.md
│   └── ...
├── .bookify/                   # Generated scripts and plans
│   ├── merge_chapters.py       # Generated merge script
│   ├── file_mapping.json       # Which files go into which chapters
│   ├── navigation_plan.json    # Navigation structure
│   └── cleanup_log.txt         # What was removed/fixed
└── assets/                     # Any images/resources (if present)
```

## Text Preservation Rules
### What TO Remove:
- Page numbers (e.g., "Page 47", "- 23 -")
- Running headers/footers that repeat across pages
- OCR scan artifacts (strange characters, obvious errors)
- Excessive whitespace and blank lines
- Page break indicators

### What TO Fix:
- Sentences broken across page boundaries (rejoin them)
- Hyphenated words split across pages (unhyphenate if appropriate)
- Obvious OCR character recognition errors (only if clearly wrong)

### What NEVER TO Change:
- Author's original words, phrases, or sentence structure
- Technical terms, proper nouns, or specialized vocabulary
- Formatting that appears intentional (lists, emphasis, etc.)
- Content meaning or intent
- Paragraph structure or organization

## Script Generation Requirements
The merge script should:
1. **Be reproducible and reviewable**
2. **Log all changes made** for transparency
3. **Create backups** of original files
4. **Handle edge cases** (missing files, encoding issues)
5. **Validate output** after merging

## Quality Assurance
- Compare total word count before/after (should be nearly identical)
- Spot-check random sections to ensure content preservation
- Validate all navigation links work correctly
- Ensure chapter breaks make logical sense
- Verify no meaningful content was lost or altered

## Execution Notes
- **Priority 1**: Content preservation over perfect formatting
- **Priority 2**: Logical chapter organization
- **Priority 3**: Navigation and cross-references
- Use clear, descriptive commit messages if version control is available
- Document any ambiguous decisions in the cleanup log
- When in doubt about removing something, preserve it
