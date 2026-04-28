"""
Section extractor for 10-K, 10-Q, and 20-F filings.

10-K / 20-F use SEC item numbers we can anchor on:
    Item 1A  -> Risk Factors
    Item 7   -> Management's Discussion & Analysis (MD&A)
    Item 7A  -> Quantitative & Qualitative Disclosures about Market Risk

10-Q uses different anchors:
    Part I, Item 2  -> MD&A
    Part II, Item 1A -> Risk Factors (updates only)

Filings are HTML, often with deeply nested inline styling and iXBRL tags. We
strip to plain text first, then locate sections by item-number regex on the
flattened text. This is more robust than walking the DOM because filers use
wildly different table-of-contents structures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup


@dataclass
class ExtractedSections:
    risk_factors: Optional[str]
    mda: Optional[str]
    market_risk: Optional[str]    # 10-K Item 7A, often useful
    form_type: str
    char_counts: dict[str, int]   # quick QA

    def summary(self) -> str:
        return (
            f"Form: {self.form_type}\n"
            f"  Risk Factors:  {self.char_counts.get('risk_factors', 0):>8,} chars\n"
            f"  MD&A:          {self.char_counts.get('mda', 0):>8,} chars\n"
            f"  Market Risk:   {self.char_counts.get('market_risk', 0):>8,} chars"
        )


# --- HTML to text -------------------------------------------------------------

def html_to_text(html: str) -> str:
    """Strip HTML, iXBRL tags, and excess whitespace."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements outright
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Tables sometimes contain prose, sometimes financial data; keep their text
    text = soup.get_text(separator="\n")

    # Collapse whitespace; preserve paragraph breaks
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Section anchors ----------------------------------------------------------

# Item headings come in many flavours: "Item 1A.", "ITEM 1A —", "Item 1A:", etc.
# We anchor at start-of-line (or start of text) to avoid matching inline phrases
# like "as required by Item 7A". Real headings sit at the start of a line in the
# flattened text we produced.
def _item_pattern(item: str) -> re.Pattern:
    # `item` like "1A" or "7" or "7A"
    return re.compile(
        rf"(?:^|\n)\s*item\s+{re.escape(item)}\b[\s\.\-–—:]*",
        re.IGNORECASE,
    )


def _find_section(
    text: str,
    start_item: str,
    end_items: tuple[str, ...],
) -> Optional[str]:
    """Find content from `start_item` heading up to the next item in `end_items`.

    Filings include the item heading twice — once in the table of contents and
    once in the body. We pick the *last* occurrence of the start anchor (which
    is the body), then look for the *first* occurrence of any end anchor that
    appears after it.
    """
    start_pat = _item_pattern(start_item)
    starts = list(start_pat.finditer(text))
    if not starts:
        return None

    # Last occurrence == body (TOC entries come first)
    section_start = starts[-1].end()
    body = text[section_start:]

    # Find the earliest end anchor in the remaining body
    earliest_end = len(body)
    for end_item in end_items:
        m = _item_pattern(end_item).search(body)
        if m and m.start() < earliest_end:
            earliest_end = m.start()

    section = body[:earliest_end].strip()

    # Sanity check: a real section is at least ~150 chars. Below that, we're
    # almost certainly looking at a TOC entry, a heading-only page, or a parser
    # confusion. 10-Q updates can be brief, so we don't want this too high.
    if len(section) < 150:
        return None
    return section


# --- Public API ---------------------------------------------------------------

def extract_sections(html: str, form_type: str) -> ExtractedSections:
    """Extract MD&A, Risk Factors, and Market Risk sections from a filing."""
    text = html_to_text(html)
    form = form_type.upper().strip()

    risk_factors: Optional[str] = None
    mda: Optional[str] = None
    market_risk: Optional[str] = None

    if form in ("10-K", "20-F"):
        # 10-K item ordering: 1, 1A, 1B, 1C, 2, ..., 7, 7A, 8, 9, ...
        risk_factors = _find_section(text, "1A", end_items=("1B", "1C", "2", "3"))
        mda          = _find_section(text, "7",  end_items=("7A", "8"))
        market_risk  = _find_section(text, "7A", end_items=("8", "9"))

    elif form == "10-Q":
        # 10-Q is split into Part I and Part II. MD&A lives in Part I, Item 2;
        # Risk Factor *updates* live in Part II, Item 1A. Anchors are the same
        # item codes, so we accept whichever match yields content.
        mda          = _find_section(text, "2",  end_items=("3", "4"))
        risk_factors = _find_section(text, "1A", end_items=("2", "3", "4", "5"))
        # 10-Qs don't have a separate Item 7A — quantitative market risk is
        # rolled into Part I Item 3.
        market_risk  = _find_section(text, "3",  end_items=("4",))

    return ExtractedSections(
        risk_factors=risk_factors,
        mda=mda,
        market_risk=market_risk,
        form_type=form,
        char_counts={
            "risk_factors": len(risk_factors) if risk_factors else 0,
            "mda":          len(mda) if mda else 0,
            "market_risk":  len(market_risk) if market_risk else 0,
        },
    )
