"""Tests for the section extractor. No network calls."""

import pytest

from src.parsers.section_extractor import extract_sections, html_to_text


# Synthetic 10-K with both a TOC entry and a body for each item.
# The extractor must pick the body version, not the TOC version.
SAMPLE_10K = """
<html><body>
<h1>ACME BANK 10-K</h1>

<h2>Table of Contents</h2>
<p>Item 1A. Risk Factors ........... 12</p>
<p>Item 7. Management's Discussion ........... 45</p>
<p>Item 7A. Quantitative Disclosures ........... 78</p>
<p>Item 8. Financial Statements ........... 90</p>

<h2>Item 1. Business</h2>
<p>Acme Bank is a regional bank.</p>

<h2>Item 1A. Risk Factors</h2>
<p>Our credit risk exposure has increased due to elevated default rates in our commercial portfolio.
Provision for credit losses rose 18% year over year. We are also exposed to cyber attacks,
and a successful ransomware event could materially impact operations. Liquidity coverage
remains above regulatory minimums but funding risk is heightened in stressed scenarios.</p>
<p>This section continues with several more paragraphs of detailed risk disclosure that
would normally span many pages in a real filing. Climate transition risk and ESG factors
are increasingly material to our business planning.</p>

<h2>Item 1B. Unresolved Staff Comments</h2>
<p>None.</p>

<h2>Item 7. Management's Discussion and Analysis</h2>
<p>Net interest income grew 5% driven by higher rates. Our trading book performed well
despite market volatility. Operational expenses remained controlled.</p>
<p>This section continues for many pages with detailed financial commentary on our segments,
liquidity position, capital ratios, and forward-looking statements.</p>

<h2>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h2>
<p>Our value-at-risk measure at the 99% confidence level was $42 million. Interest rate
risk is managed via our asset-liability committee. Foreign exchange risk is hedged
through forward contracts and natural offsets in the balance sheet. Equity price risk
in the trading book is monitored daily.</p>
<p>This section continues with VAR breakdowns by trading desk, detailed sensitivity
analysis as required by Item 7A, scenario stress tests, and counterparty exposure
tables. We disclose VAR by risk class (rates, FX, equity, credit, commodity) and
the concentration of our largest counterparty exposures relative to regulatory
capital.</p>

<h2>Item 8. Financial Statements</h2>
<p>See the consolidated financial statements.</p>
</body></html>
"""


def test_html_to_text_strips_tags():
    text = html_to_text("<p>Hello <b>world</b></p>")
    assert "Hello" in text
    assert "<" not in text
    assert ">" not in text


def test_html_to_text_collapses_whitespace():
    text = html_to_text("<p>Foo\n\n\n\n   bar    baz</p>")
    assert "Foo" in text
    # Should not have runs of more than 2 newlines
    assert "\n\n\n" not in text


def test_extract_10k_sections():
    result = extract_sections(SAMPLE_10K, "10-K")

    assert result.form_type == "10-K"
    assert result.risk_factors is not None, "Risk Factors should be extracted"
    assert result.mda is not None, "MD&A should be extracted"
    assert result.market_risk is not None, "Market Risk should be extracted"


def test_extract_finds_body_not_toc():
    """Critical: the extractor must skip the TOC entry and pick the body."""
    result = extract_sections(SAMPLE_10K, "10-K")
    # Body content for Item 1A mentions "credit risk", TOC does not
    assert "credit risk" in result.risk_factors.lower()
    # TOC just says "Risk Factors ........... 12"; body has substantive content
    assert len(result.risk_factors) > 200


def test_extract_respects_section_boundaries():
    """Item 7 content should not bleed into Item 7A or Item 8."""
    result = extract_sections(SAMPLE_10K, "10-K")
    # MD&A discusses NII; should not include VAR ($42 million is in 7A)
    assert "$42 million" not in result.mda
    # MD&A should not include Item 8's "consolidated financial statements"
    assert "consolidated financial statements" not in result.mda


def test_extract_handles_missing_sections():
    """Filing without recognizable items returns Nones, doesn't crash."""
    result = extract_sections("<html><body><p>No items here.</p></body></html>", "10-K")
    assert result.risk_factors is None
    assert result.mda is None


def test_char_counts_populated():
    result = extract_sections(SAMPLE_10K, "10-K")
    assert result.char_counts["risk_factors"] > 0
    assert result.char_counts["mda"] > 0
    # Sanity: char count matches actual length
    assert result.char_counts["risk_factors"] == len(result.risk_factors)
