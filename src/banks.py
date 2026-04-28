"""
Bank registry.

Each entry tells the platform:
  - which bank we're tracking,
  - the source it files into (SEC EDGAR, or annual-report PDF), and
  - the lookup key needed to fetch its filings.

US/global banks file 10-Ks and 10-Qs with the SEC; African banks publish PDF
annual reports on their corporate sites. Same downstream pipeline, two ingestion
paths.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    SEC_EDGAR = "sec_edgar"          # 10-K / 10-Q on EDGAR
    ANNUAL_REPORT_PDF = "pdf_report"  # PDF on bank website


@dataclass(frozen=True)
class Bank:
    name: str
    ticker: Optional[str]
    country: str
    source: SourceType
    cik: Optional[str] = None         # 10-digit SEC CIK, zero-padded
    annual_report_url: Optional[str] = None  # for PDF-source banks

    def __str__(self) -> str:
        loc = f"{self.country}"
        return f"{self.name} ({self.ticker or '—'}) [{loc}]"


# CIKs are SEC-assigned and stable. Zero-padded to 10 digits per EDGAR convention.
BANKS: list[Bank] = [
    # --- US bulge-bracket ---
    Bank("JPMorgan Chase", "JPM", "US", SourceType.SEC_EDGAR, cik="0000019617"),
    Bank("Bank of America", "BAC", "US", SourceType.SEC_EDGAR, cik="0000070858"),
    Bank("Citigroup", "C", "US", SourceType.SEC_EDGAR, cik="0000831001"),
    Bank("Wells Fargo", "WFC", "US", SourceType.SEC_EDGAR, cik="0000072971"),
    Bank("Goldman Sachs", "GS", "US", SourceType.SEC_EDGAR, cik="0000886982"),
    Bank("Morgan Stanley", "MS", "US", SourceType.SEC_EDGAR, cik="0000895421"),

    # --- European banks with US listings (file 20-F, parser handles this too) ---
    Bank("HSBC Holdings", "HSBC", "UK", SourceType.SEC_EDGAR, cik="0001089113"),
    Bank("Barclays", "BCS", "UK", SourceType.SEC_EDGAR, cik="0000312069"),
    Bank("Deutsche Bank", "DB", "DE", SourceType.SEC_EDGAR, cik="0001159508"),

    # --- African banks (PDF annual reports) ---
    # Note: URLs change yearly; the platform treats them as runtime configuration.
    Bank(
        "Afriland First Bank",
        ticker=None,
        country="CM",
        source=SourceType.ANNUAL_REPORT_PDF,
        annual_report_url="https://www.afrilandfirstbank.com/reports/latest.pdf",
    ),
    Bank(
        "Ecobank Transnational",
        ticker="ETI.LG",
        country="TG",
        source=SourceType.ANNUAL_REPORT_PDF,
        annual_report_url="https://ecobank.com/group/investor-relations/annual-reports",
    ),
    Bank(
        "Standard Bank Group",
        ticker="SBK.JO",
        country="ZA",
        source=SourceType.ANNUAL_REPORT_PDF,
        annual_report_url="https://www.standardbank.com/sbg/standard-bank-group/investor-relations",
    ),
    Bank(
        "Attijariwafa Bank",
        ticker="ATW.CS",
        country="MA",
        source=SourceType.ANNUAL_REPORT_PDF,
        annual_report_url="https://ir.attijariwafabank.com/en/financial-information/annual-reports",
    ),
]


def get_bank(identifier: str) -> Bank:
    """Look up a bank by name (case-insensitive substring) or ticker."""
    ident = identifier.lower().strip()
    for bank in BANKS:
        if bank.ticker and bank.ticker.lower() == ident:
            return bank
        if ident in bank.name.lower():
            return bank
    raise KeyError(f"No bank matches '{identifier}'. Known: {[b.ticker or b.name for b in BANKS]}")


def banks_by_source(source: SourceType) -> list[Bank]:
    return [b for b in BANKS if b.source == source]
