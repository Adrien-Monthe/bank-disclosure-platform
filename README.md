# Bank Disclosure Intelligence Platform

A parser and analyzer for bank disclosures — pulls MD&A and Risk Factor sections from SEC 10-K/10-Q/20-F filings *and* annual report PDFs, then scores each bank against a structured risk taxonomy (credit, market, liquidity, cyber, regulatory, ESG, geopolitical, AI/tech).

Built for a graduate finance + AI exercise. Covers thirteen banks across three continents.

## Why this exists

Bank disclosures are long, dense, and inconsistently structured. A single 10-K runs hundreds of pages; comparing risk emphasis across six banks takes weeks by hand. This platform reduces that to a CLI command per bank and a JSON report you can diff.

## What's in the box

| | |
|---|---|
| **Banks tracked** | 6 US (JPM, BAC, C, WFC, GS, MS), 3 European (HSBC, Barclays, Deutsche), 4 African (Afriland, Ecobank, Standard Bank, Attijariwafa) |
| **Sources** | SEC EDGAR (US/global) + corporate PDF annual reports (African) |
| **Sections extracted** | 10-K Items 1A, 7, 7A; 10-Q Part I Item 2 + Part II Item 1A |
| **Scoring** | Keyword-density across 9 risk themes, with year-over-year deltas |
| **Tests** | 20 unit tests, no network dependency |

## Install

```bash
git clone <repo-url>
cd bank-disclosure-platform
pip install -r requirements.txt
```

The SEC requires a real contact email in the User-Agent header for any EDGAR request. Set this once:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
```

Without it, EDGAR will throttle or block the request.

## Use it

List the banks the platform tracks:

```bash
python -m src.cli list
```

Analyze a bank's most recent 10-K:

```bash
python -m src.cli analyze JPM
```

Latest 10-Q instead:

```bash
python -m src.cli analyze BAC --quarterly
```

African bank from a PDF (override the registry URL if needed):

```bash
python -m src.cli analyze "Afriland" --pdf-url https://example.com/afriland_2024.pdf
```

Save the report to `data/processed/`:

```bash
python -m src.cli analyze JPM --save
```

## What the output looks like

```json
{
  "bank_name": "JPMorgan Chase",
  "ticker": "JPM",
  "country": "US",
  "source": "SEC EDGAR",
  "source_url": "https://www.sec.gov/Archives/edgar/data/19617/...",
  "form_type": "10-K",
  "period": "2024-12-31",
  "risk_section_chars": 187432,
  "mda_section_chars": 312901,
  "top_risk_themes": [
    {"theme": "credit",       "mentions": 287, "density": 5.74},
    {"theme": "regulatory",   "mentions": 241, "density": 4.82},
    {"theme": "cyber",        "mentions": 198, "density": 3.96},
    {"theme": "market",       "mentions": 156, "density": 3.12},
    {"theme": "esg_climate",  "mentions": 102, "density": 2.04}
  ],
  "generated_at": "2026-04-28T14:32:11Z"
}
```

## Architecture

```
src/
├── banks.py                       # Registry of tracked banks + source routing
├── pipeline.py                    # Orchestration: fetch → extract → analyze
├── cli.py                         # Command-line interface
├── parsers/
│   ├── edgar_client.py            # SEC EDGAR API client (rate-limited)
│   ├── section_extractor.py       # MD&A / Risk Factors extraction
│   └── pdf_parser.py              # PDF annual report parser
└── analysis/
    └── risk_analyzer.py           # Risk taxonomy + theme density scoring
```

Two ingestion paths converge on the same downstream pipeline. EDGAR filings flow through `edgar_client → section_extractor`; PDFs flow through `pdf_parser`. Both produce text that the same `risk_analyzer` scores.

## Risk taxonomy

Nine themes, each with 5–8 keyword anchors:

`credit · market · liquidity · operational · cyber · regulatory · geopolitical · esg_climate · ai_tech`

The full keyword sets live in `src/analysis/risk_analyzer.py` and are deliberately transparent — any audit team can read the source and see exactly what triggers a score. v2 plans to layer a FinBERT classifier on top while keeping the keyword scorer as an explainable fallback.

## Tests

```bash
pytest tests/ -v
```

20 tests, all offline. Network-dependent integration tests are intentionally out-of-scope for CI; run manual smoke tests with the CLI when validating against live EDGAR.

## What's coming in v2

See [`docs/PRD.md`](docs/PRD.md). Highlights:

- Multi-year longitudinal corpus (last 5 years × all banks).
- FinBERT classifier with sentence-level evidence linking.
- Peer comparison heatmap and a lightweight web UI.
- REST API for programmatic access.

## License

MIT (placeholder for class submission).

## Acknowledgements

Built as a graduate-level technical exercise on transformer NLP applied to bank disclosures. Inspired by JPMorgan's COiN platform and the FinBERT line of work.
