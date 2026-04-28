"""Tests for the risk theme analyzer."""

import pytest

from src.analysis.risk_analyzer import (
    compare_themes,
    extract_sentences_with_keyword,
    score_themes,
)


def test_score_themes_picks_up_credit_risk():
    text = """
    Our credit risk exposure has grown materially. Non-performing loans rose,
    and provision for credit losses increased. Default rates in the commercial
    portfolio remain elevated.
    """
    scores = score_themes(text)
    top = scores[0]
    assert top.theme == "credit"
    assert top.mentions >= 3


def test_score_themes_returns_all_themes():
    """Even themes with zero mentions should appear in the output."""
    scores = score_themes("Generic text with no risk vocabulary.")
    themes = {s.theme for s in scores}
    assert "credit" in themes
    assert "cyber" in themes
    assert "esg_climate" in themes


def test_score_themes_density_calculation():
    text = "credit risk " * 100  # 1200 chars, 100 mentions of "credit risk"
    scores = score_themes(text)
    credit = next(s for s in scores if s.theme == "credit")
    # 100 mentions in 1200 chars -> density ~ 833 per 10k
    assert credit.mentions == 100
    assert credit.density > 800


def test_score_themes_empty_text():
    assert score_themes("") == []


def test_compare_themes_detects_increases():
    prior = score_themes("Standard banking operations.")  # all near zero
    current = score_themes(
        "Cyber attacks and ransomware are growing concerns. "
        "Cybersecurity is now our top priority. Phishing attempts up 40%."
    )
    deltas = compare_themes(prior, current)
    cyber_delta = next(d for d in deltas if d.theme == "cyber")
    assert cyber_delta.direction == "up"
    assert cyber_delta.delta > 0


def test_extract_sentences_with_keyword():
    text = (
        "Our credit risk grew. Trading conditions improved. "
        "Default rates rose in Q3. We saw better margins overall."
    )
    hits = extract_sentences_with_keyword(text, "default")
    assert len(hits) == 1
    assert "Default rates" in hits[0]
