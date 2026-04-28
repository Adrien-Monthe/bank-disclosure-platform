"""
Unified pipeline.

The `analyze_bank` function takes a bank identifier (ticker or name) and returns
a structured report regardless of whether the source is SEC EDGAR or a PDF
annual report. Callers (CLI, API, notebook) interact only with this layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .analysis.risk_analyzer import ThemeScore, score_themes
from .banks import Bank, SourceType, get_bank
from .parsers.edgar_client import (
    Filing,
    fetch_filing_html,
    latest_annual,
    latest_quarterly,
)
from .parsers.pdf_parser import PdfSections, extract_pdf_sections, fetch_pdf
from .parsers.section_extractor import ExtractedSections, extract_sections


@dataclass
class BankReport:
    bank_name: str
    ticker: Optional[str]
    country: str
    source: str
    source_url: Optional[str]
    form_type: Optional[str]
    period: Optional[str]
    risk_section_chars: int
    mda_section_chars: int
    top_risk_themes: list[dict]
    generated_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _theme_dicts(themes: list[ThemeScore], top_n: int = 5) -> list[dict]:
    return [
        {"theme": t.theme, "mentions": t.mentions, "density": t.density}
        for t in themes[:top_n]
    ]


def _analyze_edgar_bank(bank: Bank, prefer: str = "annual") -> BankReport:
    """Fetch + extract + analyze for an EDGAR-filing bank."""
    assert bank.cik, f"{bank.name} marked SEC_EDGAR but has no CIK"

    if prefer == "quarterly":
        filing: Optional[Filing] = latest_quarterly(bank.cik) or latest_annual(bank.cik)
    else:
        filing = latest_annual(bank.cik) or latest_quarterly(bank.cik)

    if not filing:
        raise RuntimeError(f"No filings found on EDGAR for {bank.name} (CIK {bank.cik})")

    html = fetch_filing_html(filing)
    sections: ExtractedSections = extract_sections(html, filing.form_type)

    # Combine MD&A + Risk Factors for theme scoring (both speak to risk profile)
    combined = "\n\n".join(filter(None, [sections.risk_factors, sections.mda]))
    themes = score_themes(combined)

    return BankReport(
        bank_name=bank.name,
        ticker=bank.ticker,
        country=bank.country,
        source="SEC EDGAR",
        source_url=filing.document_url,
        form_type=filing.form_type,
        period=filing.report_date or filing.filing_date,
        risk_section_chars=sections.char_counts["risk_factors"],
        mda_section_chars=sections.char_counts["mda"],
        top_risk_themes=_theme_dicts(themes),
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def _analyze_pdf_bank(bank: Bank, pdf_url_override: Optional[str] = None) -> BankReport:
    """Fetch + extract + analyze for a PDF-source bank."""
    url = pdf_url_override or bank.annual_report_url
    if not url:
        raise RuntimeError(f"{bank.name} has no annual_report_url and none was provided")

    pdf_bytes = fetch_pdf(url)
    sections: PdfSections = extract_pdf_sections(pdf_bytes)

    combined = "\n\n".join(filter(None, [sections.risk_section, sections.mda_section]))
    themes = score_themes(combined)

    return BankReport(
        bank_name=bank.name,
        ticker=bank.ticker,
        country=bank.country,
        source="Annual Report PDF",
        source_url=url,
        form_type="Annual Report",
        period=None,  # PDFs don't expose a clean period field
        risk_section_chars=sections.char_counts["risk"],
        mda_section_chars=sections.char_counts["mda"],
        top_risk_themes=_theme_dicts(themes),
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def analyze_bank(
    identifier: str,
    prefer: str = "annual",
    pdf_url_override: Optional[str] = None,
) -> BankReport:
    """Top-level entrypoint. Resolve a bank, route to the right pipeline, return a report."""
    bank = get_bank(identifier)
    if bank.source == SourceType.SEC_EDGAR:
        return _analyze_edgar_bank(bank, prefer=prefer)
    elif bank.source == SourceType.ANNUAL_REPORT_PDF:
        return _analyze_pdf_bank(bank, pdf_url_override=pdf_url_override)
    else:
        raise ValueError(f"Unknown source type: {bank.source}")


def save_report(report: BankReport, out_dir: str | Path = "data/processed") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = report.bank_name.lower().replace(" ", "_")
    path = out_dir / f"{safe_name}_{report.period or 'latest'}.json"
    path.write_text(report.to_json())
    return path
