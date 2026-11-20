# Report downloader

**Problem:** before we can answer questions about a company, we need its annual report, and we need to be sure the company exists and the report is available.

**Status:** working. Run against the real SEC, it fetched Apple's annual report for fiscal year 2026 (filed 2026-11-03).

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/saeedashrraf/earning-analysis/blob/main/notebooks/01_fetch_report.ipynb)

## Usage

```
python src/report_downloader/fetch_report.py AAPL
python src/report_downloader/fetch_report.py Apple --date 2024-06-30
python src/report_downloader/fetch_report.py NVDA --date 2024
python src/report_downloader/fetch_report.py Siemens
```

Example output:

```
Saved Apple Inc. 10-K (filed 2026-11-03) to data/AAPL/10-K_2026-11-03.htm
```

- No date: the newest annual report.
- `--date 2024-06-30`: the newest one filed on or before that day.
- `--date 2024`: the same, counted to the end of that year.

If the report found was filed in an earlier year than the date asked for, the script prints a warning.

## How it works

```
"AAPL" or "Apple"  (+ optional date)
   │
1. find_company      ticker or name → one company
   │                 ✗ "Unknown company"
   │
2. find_report       newest annual report on or before the date
   │                 ✗ "No annual report on or before <date>"
   │
3. download_report   save the file
   │                 ✗ "Report not accessible"
   ▼
data/AAPL/10-K_<filing date>.htm          (SEC companies)
data/SIEGY/annual-report_<date>.pdf       (other companies)
```

## Two sources

- **SEC companies** (Apple, Nvidia): found in the SEC's company list. Their 10-K is located through the SEC's filing list.
- **Other companies** (Siemens): listed in `other_companies.json`, with a link to each year's report keyed by its publication date. Adding a company means adding one entry there.

## Components

| Function | What it does |
|---|---|
| `load_cached_json` | Returns JSON from a saved file. Re-downloads only when the copy is missing or over a month old. |
| `load_companies` | Returns the companies from `other_companies.json`, followed by the SEC's list. The SEC list is saved as `sec_companies.json` on first run. |
| `find_company` | Matches a ticker or name to one company. If several match, it lists them and asks the user to pick by number, ticker or full name. |
| `find_report` | Collects the company's reports, from the SEC filing list (saved as `data/<ticker>/filings.json`) or from `other_companies.json`, and picks the newest on or before the date. Amendments (10-K/A) are skipped. |
| `download_report` | Saves the report to `data/<ticker>/`. Skips the download if the file is already there. The SEC contact details are sent only to the SEC. |
| `main` | Reads the command-line inputs, runs the three steps, and prints the saved path or the error. |

## Setup

The SEC requires automated tools to identify themselves with a name and contact email. Set it once, outside the code:

```
export SEC_USER_AGENT="Your Name your@email.com"
```

In Colab:

```python
import os
os.environ["SEC_USER_AGENT"] = "Your Name your@email.com"
```

## Limits

- Companies outside the SEC must be added to `other_companies.json` by hand, with one new link per year.
- Saved lists are reused for a month, so a report filed in the last few weeks may not appear until the saved filing list expires.
- The SEC's main filing list covers recent years only.
