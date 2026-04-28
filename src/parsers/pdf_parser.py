"""
PDF parser for annual reports.

African banks (Afriland, Ecobank, Standard Bank, Attijariwafa) don't file with
the SEC. They publish annual reports as PDFs on their corporate sites. The PDFs
are not as standardized as 10-Ks — section names vary by issuer and language —
so we accept a list of likely heading patterns and locate the first match.

Built on pypdf for robust text extraction. Falls back gracefully when a section
isn't found rather than throwing.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Optional

import requests
from pypdf import PdfReader


# Heading variants we've seen in African bank annual reports across English/French.
RISK_HEADINGS = (
    "risk management",
    "risk factors",
    "principal risks",
    "gestion des risques",       # FR: "Risk management"
    "facteurs de risque",        # FR: "Risk factors"
    "principaux risques",        # FR: "Principal risks"
)

MDA_HEADINGS = (
    "management discussion",
    "management's discussion",
    "operating and financial review",
    "financial review",
    "business review",
    "rapport de gestion",        # FR: "Management report"
    "revue financière",          # FR: "Financial review"
    "revue financiere",          # accent-stripped variant
)


@dataclass
class PdfSections:
    risk_section: Optional[str]
    mda_section: Optional[str]
    page_count: int
    char_counts: dict[str, int]


def fetch_pdf(url: str, timeout: int = 60) -> bytes:
    """Download a PDF as bytes. Caller handles caching."""
    headers = {"User-Agent": "Mozilla/5.0 (Bank Disclosure Platform)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def pdf_to_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract all text from a PDF along with page count."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            # Some pages have unparseable content (scanned images, exotic fonts).
            # We skip them rather than fail the whole document.
            pages_text.append("")
    return "\n\n".join(pages_text), len(reader.pages)


def _find_heading_section(
    text: str,
    headings: tuple[str, ...],
    max_chars: int = 50_000,
) -> Optional[str]:
    """Locate the first occurrence of any heading and return up to max_chars after.

    Annual report PDFs don't have clean section terminators, so we cap the
    extracted length. 50k chars is roughly 8–10 pages of dense prose, which
    covers any reasonable risk or MD&A section.
    """
    lower = text.lower()
    earliest = -1
    for heading in headings:
        idx = lower.find(heading)
        if idx != -1 and (earliest == -1 or idx < earliest):
            earliest = idx
    if earliest == -1:
        return None

    section = text[earliest : earliest + max_chars]
    # Trim trailing whitespace and collapse runs of blank lines
    section = re.sub(r"\n{3,}", "\n\n", section).strip()
    return section if len(section) > 150 else None


def extract_pdf_sections(pdf_bytes: bytes) -> PdfSections:
    """Extract risk and MD&A-equivalent sections from a bank annual report PDF."""
    text, page_count = pdf_to_text(pdf_bytes)
    risk = _find_heading_section(text, RISK_HEADINGS)
    mda = _find_heading_section(text, MDA_HEADINGS)
    return PdfSections(
        risk_section=risk,
        mda_section=mda,
        page_count=page_count,
        char_counts={
            "risk":  len(risk) if risk else 0,
            "mda":   len(mda) if mda else 0,
        },
    )
