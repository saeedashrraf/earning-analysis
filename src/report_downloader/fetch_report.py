"""Download a company's annual report from the SEC."""

import json
import os
import time
from pathlib import Path

import requests

SEC_HEADERS = {"User-Agent": os.environ.get("SEC_USER_AGENT", "")}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANIES_FILE = Path(__file__).parent / "sec_companies.json"
MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # one month


def load_companies() -> list[dict]:
    """Return the SEC company list, refreshing the saved copy monthly."""
    is_fresh = (
        COMPANIES_FILE.exists()
        and time.time() - COMPANIES_FILE.stat().st_mtime < MAX_AGE_SECONDS
    )
    if not is_fresh:
        response = requests.get(TICKERS_URL, headers=SEC_HEADERS, timeout=30)
        response.raise_for_status()
        COMPANIES_FILE.write_text(response.text)
    return list(json.loads(COMPANIES_FILE.read_text()).values())


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
