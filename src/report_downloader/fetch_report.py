"""Download a company's annual report (10-K) from the SEC."""

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
    """Return the SEC's list of companies."""
    return list(load_cached_json(TICKERS_URL, COMPANIES_FILE).values())


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
    """Return the newest 10-K filed on or before as_of (default: today)."""
    cutoff = as_of or date.today()
    url = f"https://data.sec.gov/submissions/CIK{company['cik_str']:010d}.json"
    file = DATA_DIR / company["ticker"] / "filings.json"
    recent = load_cached_json(url, file)["filings"]["recent"]

    filings = zip(recent["form"], recent["filingDate"],
                  recent["accessionNumber"], recent["primaryDocument"])
    for form, filed, accession, document in filings:
        if form == "10-K" and date.fromisoformat(filed) <= cutoff:
            if as_of and filed[:4] != str(as_of.year):
                print(f"Warning: no 10-K was filed in {as_of.year} by {as_of}. "
                      f"Using the previous one, filed {filed}.")
            return {"filed": filed, "accession": accession, "document": document}
    raise LookupError(f"No annual report on or before {cutoff}")


def download_report(company: dict, report: dict) -> Path:
    """Save the report to data/<ticker>/ and return its path."""
    file = DATA_DIR / company["ticker"] / f"10-K_{report['filed']}.htm"
    if file.exists():
        return file

    accession = report["accession"].replace("-", "")
    url = (f"https://www.sec.gov/Archives/edgar/data/"
           f"{company['cik_str']}/{accession}/{report['document']}")
    response = requests.get(url, headers=SEC_HEADERS, timeout=60)
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
        sys.exit(f"Error: could not reach the SEC ({error})")
    print(f"Saved {company['title']} 10-K (filed {report['filed']}) to {path}")


if __name__ == "__main__":
    main()
