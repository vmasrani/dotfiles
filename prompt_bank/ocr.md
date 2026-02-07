
Master Prompt v3: Image + OCR → Structurally Faithful Markdown

You are given:
	1.	One or more images of technical manual pages
	2.	OCR-extracted text for those images (OCR text may have incorrect order, broken columns, duplicated numbers, or layout loss)

The pages may include component location diagrams, alignment diagrams, legends, fuse/relay maps, tables, flowcharts, or explanatory text.

⸻

Ground Truth Rules
	•	Visual layout dominates structure and grouping
	•	OCR text is advisory, not authoritative, for layout or ordering
	•	Do not assume the OCR reading order is correct

⸻

Extraction Strategy

1. Page Segmentation
Identify and separate:
	•	Page titles and section headers
	•	Diagrams / figures
	•	Alignment maps (numbered boxes)
	•	Legends or numbered lists mapping IDs → components
	•	Notes or cross-references (“Refer to…”)

Each becomes its own Markdown section.

⸻

2. Structural Mapping Rules
Use these mappings only when visually justified:

Visual Pattern	Markdown Representation
Numbered components with descriptions	Table: `ID
Alignment diagrams (boxes with numbers only)	Table or grid-style table labeled “Alignment”
Fuse / relay lists split across columns	Single unified table (preserve numbering)
Diagram labels pointing to numbers	Table row mapping number → name
“Refer to figure / right side” notes	Footnote or Notes section


⸻

3. Tables: Preferred Canonical Form
When a legend exists, always normalize into a single table, even if the page visually splits it across columns.

Example canonical headers:
	•	Position
	•	Component ID
	•	Component Name / Function
	•	Notes (only if explicitly present)

Do not create multiple tables for the same logical list unless the page clearly separates systems.

⸻

4. OCR Reconciliation Rules
	•	Repair OCR errors only when the intended text is visually obvious
	•	Preserve original abbreviations (OPT., RY-, FU-)
	•	Preserve numbering exactly (do not renumber or reorder)
	•	If OCR merges columns, reconstruct logically using numbering
	•	If OCR text exists but cannot be placed confidently, omit it

Never guess.

⸻

5. Alignment & Location Diagrams
When a diagram shows numbered physical positions without text:
	•	Create a separate section:
	•	Title: Relay Box 1 Alignment / Fuse Alignment
	•	Represent as a table or grid preserving relative order
	•	Do not attach meaning unless explicitly given elsewhere

If meaning exists in a legend, link via shared numbers, not prose.

⸻

6. Cross-References
Preserve instructional references verbatim:
	•	“Refer to the right figure…”
	•	“Serial No. XXXX and up”

These belong in:
	•	Section subtitles
	•	Or a short Notes subsection

⸻

Output Constraints
	•	Markdown only
	•	No explanations or commentary
	•	One section per logical structure
	•	Prefer lossless transcription over readability if trade-offs arise

⸻

Design Principle (Implicit but Enforced)

Treat the page as a database schema, not a picture.

