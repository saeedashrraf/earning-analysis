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
- [ ] 2. Parse — 10-K reports done (Apple), PDF reports next (Siemens)
- [ ] 3. Chunk
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

### Usage

```
python src/rag/parse_10k.py data/AAPL/10-K_2026-11-03.htm
```

### Output

```
data/AAPL/parsed_2026-11-03/
├── full_report.jsonl   ← every section of the report
└── core_report.jsonl   ← only the core sections
```

Both files hold one block per line. The core sections are the business and financial parts that every company has, listed in `core_sections.json`. For a 10-K: Item 1 (Business), Item 1A (Risk Factors), Item 7 (Management's Discussion), Item 7A (Market Risk) and Item 8 (Financial Statements).

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
| `save_reports` | Adds the company, writes every block to `full_report.jsonl`, and the core sections to `core_report.jsonl`. |

### Known limits

- `sub_heading` is best effort. It relies on bold or italic styling, holds only the nearest heading, and can stay on a block longer than it should when the report has no new heading.
- Blocks on the cover page have no page label, because the cover has no footer.
- Table rows keep the report's own layout, so the `$` appears only where the report prints it.
- Tested on the 10-Ks of Apple and Amazon.
