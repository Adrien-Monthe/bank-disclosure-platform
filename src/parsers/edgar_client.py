"""
SEC EDGAR client.

EDGAR exposes a JSON submissions API at data.sec.gov that lists every filing
for a given CIK. We use it to find the most recent 10-K (annual) or 10-Q
(quarterly) filing, then download the primary document URL.

EDGAR requires a User-Agent header with a real contact email — anonymous
requests are throttled or blocked. Set the contact via the SEC_USER_AGENT
environment variable in production.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterator, Optional

import requests

EDGAR_BASE = "https://data.sec.gov"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# EDGAR rate limit: 10 requests/second per the SEC fair-access policy.
# We keep a generous buffer so a parallel run doesn't hit the wall.
_MIN_REQUEST_INTERVAL_S = 0.15
_last_request_at = 0.0


def _user_agent() -> str:
    return os.getenv(
        "SEC_USER_AGENT",
        "Bank Disclosure Platform research@example.com",
    )


def _throttled_get(url: str, timeout: int = 30) -> requests.Response:
    """GET with EDGAR-friendly headers and rate limiting."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_REQUEST_INTERVAL_S:
        time.sleep(_MIN_REQUEST_INTERVAL_S - elapsed)

    headers = {
        "User-Agent": _user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Host": url.split("/")[2],
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    _last_request_at = time.monotonic()
    resp.raise_for_status()
    return resp


@dataclass(frozen=True)
class Filing:
    cik: str
    accession_number: str   # e.g. "0000019617-25-000123"
    form_type: str          # "10-K", "10-Q", "20-F", etc.
    filing_date: str        # ISO date "YYYY-MM-DD"
    primary_document: str   # filename of the main HTML/htm document
    report_date: Optional[str] = None  # period of report

    @property
    def document_url(self) -> str:
        """Public URL of the primary filing document on EDGAR Archives."""
        # Accession number stripped of dashes is used in the path
        accession_clean = self.accession_number.replace("-", "")
        cik_int = int(self.cik)  # path uses unpadded CIK
        return f"{ARCHIVES_BASE}/{cik_int}/{accession_clean}/{self.primary_document}"


def list_filings(
    cik: str,
    form_types: tuple[str, ...] = ("10-K", "10-Q", "20-F"),
    limit: int = 5,
) -> list[Filing]:
    """Return the most recent filings of the requested form types for a CIK.

    Pulls from the EDGAR submissions endpoint which returns the most recent
    1,000 filings inline. For our purposes (latest 10-K/10-Q), this is enough.
    """
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    data = _throttled_get(url).json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    out: list[Filing] = []
    for form, acc, fdate, pdoc, rdate in zip(forms, accessions, dates, primary_docs, report_dates):
        if form not in form_types:
            continue
        out.append(Filing(
            cik=cik,
            accession_number=acc,
            form_type=form,
            filing_date=fdate,
            primary_document=pdoc,
            report_date=rdate or None,
        ))
        if len(out) >= limit:
            break
    return out


def fetch_filing_html(filing: Filing) -> str:
    """Download the primary document of a filing as raw HTML/text."""
    return _throttled_get(filing.document_url).text


def latest_annual(cik: str) -> Optional[Filing]:
    """Most recent 10-K (US filers) or 20-F (foreign private issuers)."""
    filings = list_filings(cik, form_types=("10-K", "20-F"), limit=1)
    return filings[0] if filings else None


def latest_quarterly(cik: str) -> Optional[Filing]:
    filings = list_filings(cik, form_types=("10-Q",), limit=1)
    return filings[0] if filings else None
