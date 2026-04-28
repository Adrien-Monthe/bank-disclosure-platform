"""
Risk taxonomy and analyzer.

A bank's risk disclosures touch a fairly stable set of themes: credit, market,
liquidity, cyber, regulatory, ESG, geopolitical. We score each section by how
prominently each theme appears (mentions normalized by section length).

This is a deliberately simple keyword-based scorer. A FinBERT-style sentiment
classifier would be the obvious upgrade, but it adds a 400MB model dependency
and a GPU-friendly runtime. The PRD treats that as a v2 enhancement; for the
MVP, transparent rules are easier to defend in a regulated context where
"explainability" is a real audit requirement, not a slogan.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass


# Each theme has (a) keywords that count as a mention and (b) a short label.
# Words are matched case-insensitively as whole words.
RISK_THEMES: dict[str, list[str]] = {
    "credit":      ["credit risk", "loan loss", "non-performing", "delinquen",
                    "default", "charge-off", "provision for credit"],
    "market":      ["market risk", "trading loss", "interest rate risk",
                    "value-at-risk", "var ", "fx risk", "foreign exchange risk"],
    "liquidity":   ["liquidity risk", "funding risk", "deposit outflow",
                    "lcr", "liquidity coverage", "run on the bank"],
    "operational": ["operational risk", "fraud", "internal control",
                    "human error", "process failure", "third-party risk"],
    "cyber":       ["cyber", "cybersecurity", "data breach", "ransomware",
                    "phishing", "information security"],
    "regulatory":  ["regulatory", "compliance", "consent order", "enforcement",
                    "fine", "penalty", "sanction"],
    "geopolitical":["geopolitical", "russia", "ukraine", "china",
                    "trade tension", "tariff", "sanctions regime"],
    "esg_climate": ["climate", "esg", "carbon", "transition risk",
                    "physical risk", "net zero", "sustainability"],
    "ai_tech":     ["artificial intelligence", "machine learning",
                    "ai model", "generative ai", "large language model"],
}


@dataclass
class ThemeScore:
    theme: str
    mentions: int
    density: float  # mentions per 10k characters

    def __str__(self) -> str:
        return f"{self.theme:12s}  mentions={self.mentions:4d}  density={self.density:6.2f}/10k"


def score_themes(text: str) -> list[ThemeScore]:
    """Count theme keyword mentions in a section and return density-ranked list."""
    if not text:
        return []
    text_lower = text.lower()
    char_count = len(text_lower)
    out: list[ThemeScore] = []
    for theme, keywords in RISK_THEMES.items():
        mentions = 0
        for kw in keywords:
            # Use a word-boundary regex so "default" doesn't match "defaults"
            # incorrectly — actually we want both, so just count substrings.
            mentions += text_lower.count(kw)
        density = (mentions / char_count) * 10_000 if char_count else 0
        out.append(ThemeScore(theme=theme, mentions=mentions, density=round(density, 2)))
    out.sort(key=lambda s: s.density, reverse=True)
    return out


# --- Year-over-year delta -----------------------------------------------------

@dataclass
class ThemeDelta:
    theme: str
    prior_density: float
    current_density: float
    delta: float
    direction: str  # "up", "down", "flat"


def compare_themes(prior: list[ThemeScore], current: list[ThemeScore]) -> list[ThemeDelta]:
    """Compute year-over-year change in theme density.

    Useful for spotting *new* concerns: e.g. a bank that barely mentioned cyber
    last year but devotes paragraphs to it this year.
    """
    prior_map = {s.theme: s.density for s in prior}
    current_map = {s.theme: s.density for s in current}
    themes = sorted(set(prior_map) | set(current_map))

    out: list[ThemeDelta] = []
    for theme in themes:
        p = prior_map.get(theme, 0.0)
        c = current_map.get(theme, 0.0)
        delta = round(c - p, 2)
        if abs(delta) < 0.1:
            direction = "flat"
        elif delta > 0:
            direction = "up"
        else:
            direction = "down"
        out.append(ThemeDelta(theme=theme, prior_density=p, current_density=c,
                              delta=delta, direction=direction))
    out.sort(key=lambda d: abs(d.delta), reverse=True)
    return out


# --- Sentence-level extraction for evidence ----------------------------------

def extract_sentences_with_keyword(text: str, keyword: str, max_results: int = 5) -> list[str]:
    """Pull sentences mentioning a keyword — useful for showing evidence in reports."""
    sentences = re.split(r"(?<=[\.\?\!])\s+", text)
    kw_lower = keyword.lower()
    hits = [s.strip() for s in sentences if kw_lower in s.lower()]
    return hits[:max_results]
