# Part 1: RAG

**Problem:** LLMs invent facts. Every answer must point to the exact place in the filing it came from, so it can be checked.

## How it works

```
1. Load      download the annual report
     │
2. Parse     report → blocks, each labeled with its section and page
     │
3. Chunk     group blocks into pieces sized for search
     │
4. Embed     turn each piece into a vector
     │
5. Retrieve  find the pieces closest to a question
     │
6. Answer    LLM writes the answer, citing its sources
```

## Progress

- [x] 1. Load — done by the [report downloader](../report_downloader/)
- [x] 2. Parse — 10-K reports (Apple, Amazon) and PDF reports (Siemens)
- [ ] 3. Chunk ← next
- [ ] 4. Embed
- [ ] 5. Retrieve
- [ ] 6. Answer

## Step 2: Parse

A **block** is one paragraph or one whole table, exactly as the report has it. Every block carries labels that say where it came from:

```json
{"company": "AAPL", "section": "Item 7",
 "section_title": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
 "sub_heading": "Americas", "page": "Apple Inc. | 2026 Form 10-K | 25", "type": "text",
 "text": "Americas net sales increased during 2026 compared to 2025 due to higher net sales of iPhone, Services and Mac."}
```

Both parsers produce the same seven fields, so every later step treats all companies alike:

| Label | Apple (10-K) | Siemens (PDF) |
|---|---|---|
| `section` | Item 7 | Combined Management Report |
| `section_title` | Management's Discussion and Analysis... | 2. Financial performance system |
| `sub_heading` | Americas | 2.1 Revenue growth |
| `page` | Apple Inc. \| 2026 Form 10-K \| 25 | 6 |

### Usage

```
python src/rag/parse_10k.py data/AAPL/10-K_2026-11-03.htm
python src/rag/parse_pdf.py data/SIEGY/annual-report_2025-12-03.pdf
```

The PDF parser takes about a minute for a 335-page report.

### Output

```
data/AAPL/parsed_2026-11-03/
├── full_report.jsonl   ← every section of the report
└── core_report.jsonl   ← only the core sections
```

Both files hold one block per line. The core sections are the business and financial parts that every company has, listed in `core_sections.json`:

- **10-K:** Item 1 (Business), Item 1A (Risk Factors), Item 7 (Management's Discussion), Item 7A (Market Risk), Item 8 (Financial Statements)
- **Siemens:** Combined Management Report, Consolidated Financial Statements, Five-Year Summary

| Company | Full report | Core report |
|---|---|---|
| Apple | 445 blocks | 358 blocks |
| Amazon | 629 blocks | 529 blocks |
| Siemens | 2,689 blocks | 778 blocks |

### Components of `parse_10k.py`

```
10-K .htm
   │
html_to_blocks   strip markup → headings, paragraphs, tables, page breaks
   │
label_pages      tag each block with its page footer; drop footers and headers
   │
label_sections   tag each block with its Item and nearest sub-heading
   │
save_reports     write full_report.jsonl and core_report.jsonl
```

| Function | What it does |
|---|---|
| `html_to_blocks` | Removes the hidden metadata, then turns each text `<div>` into a paragraph and each `<table>` into one table block with a line per row. Text that is all bold or italic, up to 40 words, is marked as a heading. |
| `merge_symbols` | Joins a lone `$` to the number after it and a lone `%` to the number before it, so a row reads `$198,083 \| 11%`. |
| `label_pages` | The last block before each page break is the footer. It becomes the page label, exactly as printed, and is then removed from the content. |
| `label_sections` | Finds Items by their text ("Item 7. ..."), so it does not depend on styling. Other headings become the `sub_heading` of the blocks below them. |
| `save_reports` | Adds the company, writes every block to `full_report.jsonl`, and the core sections to `core_report.jsonl`. Shared with the PDF parser. |

### Known limits of the 10-K parser

- `sub_heading` is best effort. It relies on bold or italic styling, holds only the nearest heading, and can stay on a block longer than it should when the report has no new heading.
- Blocks on the cover page have no page label, because the cover has no footer.
- Table rows keep the report's own layout, so the `$` appears only where the report prints it.
- Tested on the 10-Ks of Apple and Amazon.

### Components of `parse_pdf.py`

A PDF has no tags, so this parser reads structure from layout: font size, position on the page, and the gaps between characters.

```
PDF
 │
report_starts     the PDF's bookmarks → the reports inside it and their first pages
 │
pdf_to_lines      every line with its font size, position and columns
 │
label_sections    tag each line with its report; drop page headers and footers
 │
lines_to_blocks   join lines into headings, paragraphs and tables
 │
label_blocks      tag each block with its chapter, sub-heading and page
 │
save_reports      shared with the 10-K parser
```

| Function | What it does |
|---|---|
| `report_starts` | Reads the bookmarks. The Siemens file holds 13 separate reports, and the bookmarks give each one's name and first page. |
| `split_cells` | Splits a line into columns. A horizontal gap wider than one font size separates two columns, so a row reads `Net income \| 10,387 \| 8,992`. |
| `pdf_to_lines` | Returns every line with its most common font size, its distance from the top of the page, and its columns. |
| `label_sections` | Tags each line with its report and removes the header and footer strips of each page. |
| `body_sizes` | Finds each report's body font: the largest size used by at least 15% of its lines. The reports were typeset separately, so the sizes differ. |
| `lines_to_blocks` | A line smaller than body text, or with three or more columns, is a table row. A larger line is a heading. Lines of the same kind join into one block until a gap of more than 1.5 font sizes. |
| `chapter_sizes` | Finds each report's chapter heading size: its largest heading size that appears at least three times. |
| `label_blocks` | Chapter headings become `section_title`, smaller headings become `sub_heading`, and the PDF page number becomes `page`. Title pages and tables of contents are dropped. |

### Known limits of the PDF parser

- The page label is the PDF's page number, not the printed one. Printed numbers restart in each report and are missing on 47 pages.
- A paragraph that continues onto the next page is split into two blocks.
- Footnote marks stay attached to their words, as in "Revenue¹".
- The thresholds were chosen from the Siemens report and are tested on that one file.
