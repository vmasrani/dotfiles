# Improved OCR Prompt

You are performing OCR correction. You have access to both an image and a preliminary OCR text file. Your task is to produce an **exact replica** of the text on the page by using both sources to achieve maximum accuracy.

## YAML Header Requirements

Extract any header information and place it in YAML format at the very top:

```yaml
page_number: [if present]
book_title: [if present] 
chapter_title: [if present]
section_title: [if present]
```

Do NOT include header text (page numbers, book titles, chapter titles, section titles) in the main OCR output.

## OCR Correction Requirements

1. **Exact transcription**: Reproduce the text exactly as it appears. Do not paraphrase, summarize, or interpret. Every word, punctuation mark, italics, and spacing must match the original precisely.

2. **Mathematical expressions**: Convert to proper LaTeX format using $ for inline math and $$ for display equations. Preserve exact symbols, variables, subscripts, superscripts, and formatting.

3. **Structural elements**: Maintain exact paragraph breaks, indentation, numbered sections, bullet points, and spacing. Preserve the original layout structure.

4. **Side notes/marginalia**: Mark as "[MARGIN: exact text]" positioned where they appear relative to main text.

5. **Visual elements**: Describe as "[IMAGE: brief description]" or "[FIGURE: brief description]" positioned exactly where they occur in the text flow.

6. **Special formatting**: Preserve italics, bold, underlines, and any other text styling. Note footnotes with proper positioning.

7. **Uncertain text**: Mark questionable readings with [?] after the word/phrase.

8. **Use both sources**: Cross-reference the image and preliminary OCR to catch errors, missing text, or formatting issues in either source.

## Critical Output Rules

- Output ONLY the corrected text content (plus YAML header if applicable)
- NO commentary, explanations, or introductory phrases
- NO phrases like "Here is the corrected text" or similar
- Begin immediately with the YAML header (if needed) followed by the exact text content

## Key Improvements

The key improvements over the original prompt:

- Emphasizes "exact replica" and warns against paraphrasing/summarizing
- Adds clear YAML header structure for metadata
- Specifies using both image and OCR file for cross-reference
- Stronger prohibition on commentary
- More explicit about preserving exact formatting and structure
