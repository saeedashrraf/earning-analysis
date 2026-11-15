# Report downloader

**Problem:** before we can answer questions about a company, we need its annual report, and we need to be sure the company exists and the report is available.

## Usage

```
python src/report_downloader/fetch_report.py AAPL
python src/report_downloader/fetch_report.py Apple --date 2024-06-30
python src/report_downloader/fetch_report.py NVDA --date 2024
```

- No date: the newest annual report (10-K).
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
2. find_report       newest 10-K filed on or before the date
   │                 ✗ "No annual report on or before <date>"
   │
3. download_report   save the file
   │                 ✗ "Report not accessible"
   ▼
data/AAPL/10-K_<filing date>.htm
```

## Components

| Function | What it does |
|---|---|
| `load_cached_json` | Returns JSON from a saved file. Re-downloads only when the copy is missing or over a month old. |
| `load_companies` | Returns the SEC's company list, saved as `sec_companies.json`. |
| `find_company` | Matches a ticker or name to one company. If several match, it lists them and asks the user to pick by number, ticker or full name. |
| `find_report` | Reads the company's filing list (saved as `data/<ticker>/filings.json`) and picks the newest 10-K on or before the date. Amendments (10-K/A) are skipped. |
| `download_report` | Saves the report to `data/<ticker>/`. Skips the download if the file is already there. |
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

- Only SEC filers are supported. Companies that don't file with the SEC (such as Siemens) are reported as unknown for now.
- Saved lists are reused for a month, so a report filed in the last few weeks may not appear until the saved filing list expires.
- The SEC's main filing list covers recent years only.
