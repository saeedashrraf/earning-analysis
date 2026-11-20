"""Download a company's annual report: a 10-K from the SEC, or a listed PDF."""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

SEC_HEADERS = {"User-Agent": os.environ.get("SEC_USER_AGENT", "")}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANIES_FILE = Path(__file__).parent / "sec_companies.json"
OTHER_COMPANIES_FILE = Path(__file__).parent / "other_companies.json"
DATA_DIR = Path(__file__).parents[2] / "data"
MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # one month


def load_cached_json(url: str, file: Path) -> dict:
    """Return JSON from a saved file, re-downloading if over a month old."""
    is_fresh = file.exists() and time.time() - file.stat().st_mtime < MAX_AGE_SECONDS
    if not is_fresh:
        response = requests.get(url, headers=SEC_HEADERS, timeout=30)
        response.raise_for_status()
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(response.text)
    return json.loads(file.read_text())


def load_companies() -> list[dict]:
    """Return our own list of non-SEC companies, followed by the SEC's list."""
    others = json.loads(OTHER_COMPANIES_FILE.read_text())
    tickers = {c["ticker"] for c in others}
    sec = load_cached_json(TICKERS_URL, COMPANIES_FILE).values()
    return others + [c for c in sec if c["ticker"] not in tickers]


def find_company(query: str) -> dict:
    """Find a company by ticker or name. Asks the user if several match."""
    companies = load_companies()
    q = query.strip().lower()

    # Exact ticker or name first, otherwise names containing the query
    matches = [c for c in companies if q in (c["ticker"].lower(), c["title"].lower())]
    if not matches:
        matches = [c for c in companies if q in c["title"].lower()]

    if not matches:
        raise LookupError(f"Unknown company: {query}")
    if len(matches) == 1:
        return matches[0]

    # Several matches: show them and let the user pick
    for number, c in enumerate(matches, start=1):
        print(f"{number}. {c['title']} ({c['ticker']})")
    answer = input("Pick a number, ticker or full name: ").strip().lower()

    if answer.isdigit() and 1 <= int(answer) <= len(matches):
        return matches[int(answer) - 1]
    for c in matches:
        if answer in (c["ticker"].lower(), c["title"].lower()):
            return c
    raise LookupError(f"'{answer}' is not in the list")


def find_report(company: dict, as_of: date | None = None) -> dict:
    """Return the newest annual report published on or before as_of (default: today)."""
    cutoff = as_of or date.today()

    if "reports" in company:
        # Non-SEC company: its reports are listed in other_companies.json
        reports = [{"form": "annual-report", "filed": filed, "url": url}
                   for filed, url in company["reports"].items()]
    else:
        # SEC company: read its filing list and keep the 10-Ks
        url = f"https://data.sec.gov/submissions/CIK{company['cik_str']:010d}.json"
        file = DATA_DIR / company["ticker"] / "filings.json"
        recent = load_cached_json(url, file)["filings"]["recent"]
        archive = f"https://www.sec.gov/Archives/edgar/data/{company['cik_str']}"
        reports = [{"form": "10-K", "filed": filed,
                    "url": f"{archive}/{accession.replace('-', '')}/{document}"}
                   for form, filed, accession, document
                   in zip(recent["form"], recent["filingDate"],
                          recent["accessionNumber"], recent["primaryDocument"])
                   if form == "10-K"]

    for report in sorted(reports, key=lambda r: r["filed"], reverse=True):
        if date.fromisoformat(report["filed"]) <= cutoff:
            if as_of and report["filed"][:4] != str(as_of.year):
                print(f"Warning: no annual report was published in {as_of.year} "
                      f"by {as_of}. Using the previous one, from {report['filed']}.")
            return report
    raise LookupError(f"No annual report on or before {cutoff}")


def download_report(company: dict, report: dict) -> Path:
    """Save the report to data/<ticker>/ and return its path."""
    url = report["url"]
    name = f"{report['form']}_{report['filed']}{Path(url).suffix}"
    file = DATA_DIR / company["ticker"] / name
    if file.exists():
        return file

    # Our SEC contact details are only sent to the SEC
    headers = SEC_HEADERS if "sec.gov" in url else {}
    response = requests.get(url, headers=headers, timeout=120)
    if not response.ok:
        raise LookupError(f"Report not accessible ({response.status_code}): {url}")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(response.content)
    return file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("company", help="ticker or company name")
    parser.add_argument("--date", help="YYYY-MM-DD or YYYY")
    args = parser.parse_args()

    # A bare year like 2024 means the end of that year
    as_of = None
    if args.date:
        try:
            is_year = len(args.date) == 4
            as_of = date(int(args.date), 12, 31) if is_year else date.fromisoformat(args.date)
        except ValueError:
            sys.exit("Error: --date must be YYYY-MM-DD or YYYY.")

    if not SEC_HEADERS["User-Agent"]:
        sys.exit("Error: set SEC_USER_AGENT to your name and email first.")
    try:
        company = find_company(args.company)
        report = find_report(company, as_of)
        path = download_report(company, report)
    except LookupError as error:
        sys.exit(f"Error: {error}")
    except requests.RequestException as error:
        sys.exit(f"Error: download failed ({error})")
    print(f"Saved {company['title']} {report['form']} ({report['filed']}) to {path}")


if __name__ == "__main__":
    main()
