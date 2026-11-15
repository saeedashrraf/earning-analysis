# Report downloader

**Problem:** before we can answer questions about a company, we need its annual report, and we need to be sure the company exists and the report is available.

## How it works

```
"AAPL" or "Apple"  (+ optional date)
   │
1. find_company      ticker or name → one company
   │
2. find_report       newest 10-K filed on or before the date   (to be built)
   │
3. download_report   save it to data/                          (to be built)
```

## Components

| Function | What it does |
|---|---|
| `load_companies` | Returns the SEC's company list. Saves it to `sec_companies.json` and re-downloads only when the copy is over a month old. |
| `find_company` | Matches a ticker or name to one company. If several match, it lists them and asks the user to pick by number, ticker or full name. |

## Setup

The SEC requires a contact email in every request. Set it once, outside the code:

```
export SEC_USER_AGENT="Your Name your@email.com"
```
