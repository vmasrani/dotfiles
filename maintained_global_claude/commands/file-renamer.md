Rename this file to the format: Author Name - Title - Subtitle - YYYY-MM-DD

Rules:
- Prefer extracting **Author**, **Title**, and **Subtitle** from the PDF content (cover/title page, header, first N pages). Use the existing filename only if content is unhelpful.
- Subtitle is optional, but if it is present in the document (often after a colon), **include it** as the third segment.
- ALWAYS include a date at the end: prefer **YYYY-MM-DD**; if only a year is known, use **YYYY**.
- If already in `Author Name - Title - Subtitle - YYYY-MM-DD` (or `Author Name - Title - YYYY-MM-DD`, or `Author Name - Title - YYYY`) format, return it unchanged.
- If insufficient information to confidently identify at least **Author** and **Title**, return the original filename cleaned of extra characters.
- Return ONLY the new filename (without extension).
- Do NOT add commentary or explanations.

Examples of correct output:
1. J.K. Rowling - Harry Potter - The Philosopher's Stone - 1997
2. George Orwell - 1984 - 1949
3. Isaac Asimov - Foundation - 1951

Fallback (only if Author/Title cannot be reliably extracted):
- **Invoices**: `Invoice - CompanyName - InvNumber - YYYY-MM-DD`
- **Receipts**: `Receipt - VendorName - YYYY-MM-DD`
- **Forms/Applications/Government Documents**: `FormType - Description - Year` (prefer year if it’s an assessment/tax year)
- **Reports/Presentations**: `OrgName - Title - YYYY-MM-DD` (OrgName must be the issuer; never use literal “Report/Reports” as org)
- **Scans/Images with minimal text**: `Document Scan - YYYY-MM-DD` (exactly; no extra descriptors)
- **Generic documents**: `Title - YYYY-MM-DD`

Global output rules:
- Never use: / \ : * ? " < > |
- Replace invalid characters with hyphens or spaces
- Use title case for titles; preserve proper names; keep acronyms uppercase (AI, DNA, CEO, CRA)

Original filename:
