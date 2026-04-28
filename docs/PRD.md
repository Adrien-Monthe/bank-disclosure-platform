# Product Requirements Document — Bank Disclosure Intelligence Platform v2

**Author:** Platform Team
**Status:** Draft for review
**Last updated:** April 2026

---

## 1. Background

v1 of the platform (this repo) parses MD&A and Risk Factor disclosures from US, European, and African banks across two ingestion paths — SEC EDGAR for 10-K/10-Q/20-F filings and PDF annual reports for African banks that don't file with the SEC. It produces a structured JSON report per bank with section character counts and a top-N risk theme ranking based on keyword density.

The MVP works but is intentionally narrow: rule-based theme tagging, no longitudinal view, no comparison across banks, no UI. v2 closes those gaps and turns the parser into a usable analyst product.

## 2. Problem statement

Bank analysts, risk managers, and regulators currently read disclosures one filing at a time. A single 10-K runs 200–400 pages; a comparison across six banks across three years is functionally impossible to do by hand. Analysts settle for gut-feel summaries or rely on commercial tools (Bloomberg, S&P Capital IQ) that cost five-to-six figures a year and offer limited transparency about how their scores are derived.

**The user need:** "Show me how Bank X's risk profile changed year-over-year, and how it compares to peers, with the exact source language one click away."

## 3. Goals and non-goals

### Goals

- **G1.** Extend the parser to handle multi-year disclosure history per bank (last 5 years), not just the latest filing.
- **G2.** Provide cross-bank peer comparison on the same risk taxonomy.
- **G3.** Replace keyword density with a transformer-based sentiment + topic classifier (FinBERT or domain-tuned alternative), with the rule-based scorer kept as a fallback for explainability.
- **G4.** Deliver findings through a lightweight web UI (analyst dashboard) and a programmatic API.
- **G5.** Make every score traceable to the exact sentence(s) in the source document.

### Non-goals

- **NG1.** Real-time filing alerts. Disclosures are quarterly at fastest; near-real-time has no analyst utility and adds operational complexity.
- **NG2.** Full text search over all SEC filings. EDGAR's own full-text search already exists. We index banks, not all 8,000 filers.
- **NG3.** Financial data (balance sheet line items, ratios). XBRL parsing is a separate problem and well-served by existing tools (e.g. python-edgar, sec-api).
- **NG4.** Buy/sell investment recommendations. We surface evidence; humans decide.

## 4. User personas

- **Bank credit analyst.** Wants peer benchmarks for an upcoming credit review. Cares about which risks each bank emphasizes and how that has shifted.
- **Risk manager (internal).** Wants to see how their own bank's disclosures read against peers — both for board reporting and for peer-pressure assurance ("are we under-disclosing relative to JPM?").
- **Regulator / supervisor.** Wants longitudinal evidence of disclosure quality and consistency. Needs every assertion linked back to source.
- **Academic / research analyst.** Wants programmatic access for studies on disclosure trends.

## 5. Functional requirements

### F1. Multi-year corpus

- Ingest the last 5 fiscal years of 10-K/20-F per bank, plus the trailing 8 quarterly 10-Qs.
- For PDF-source banks, ingest the last 5 published annual reports.
- Cache extracted sections to local storage (Parquet) keyed by `(bank, form_type, period)`.

### F2. Trend analysis

- Compute year-over-year delta on each risk theme per bank.
- Surface the three themes with the largest absolute change for each bank.
- Display alongside source sentences that drove the change.

### F3. Peer comparison

- For any selected bank, display same-period theme densities for a configurable peer set.
- Default peer sets: "US bulge bracket", "European banks", "African pan-regional".
- Visualize as a heatmap (banks on one axis, themes on the other).

### F4. Transformer classifier

- Replace keyword density with FinBERT (`yiyanghkust/finbert-tone`) for sentiment, plus a multi-label topic classifier fine-tuned on a labeled subset of the existing corpus.
- Persist v1 keyword scores side-by-side; never overwrite.
- Show *both* scores in the UI when they disagree, with an explanation that the rule-based score is the audit-traceable fallback.

### F5. Sentence-level evidence

- Every theme score links to the top-5 sentences that triggered it, ranked by classifier confidence.
- Each sentence carries a deep link back to the source filing on EDGAR or the source PDF page.

### F6. API

- REST endpoints: `GET /banks`, `GET /banks/{id}/reports`, `GET /banks/{id}/themes?period=…`, `GET /compare?banks=jpm,bac&period=…`.
- API key required for any non-cached request. Cached responses are public.
- Rate limit: 60 requests/minute per key.

### F7. Web UI

- Single-page app: bank picker, period picker, theme dashboard, peer heatmap, evidence drawer.
- Read-only — no user accounts in v2, no saved searches. Bookmarkable URLs cover the same need.

## 6. Non-functional requirements

| | Requirement | Rationale |
|---|---|---|
| **N1** | EDGAR rate limit ≤ 5 req/sec sustained | SEC fair-access policy; throttling already in v1 |
| **N2** | Full corpus refresh completes in under 6 hours | Run nightly during off-peak |
| **N3** | API p95 latency < 800ms for cached responses | Analyst flow tolerates this |
| **N4** | Test coverage ≥ 80% on parser and analyzer modules | Already at this bar in v1 |
| **N5** | All scores reproducible from source given the model version | Required for regulatory traceability |
| **N6** | Model version pinned and recorded with every score | Allow re-scoring when model is updated |

## 7. Risks

- **Model drift.** A FinBERT update could change historical scores. Mitigation: pin model version per scoring run; never re-score in place.
- **PDF source instability.** African bank PDF URLs change yearly. Mitigation: keep `annual_report_url` as a runtime override; add a quarterly link-check job.
- **EDGAR access.** SEC sometimes blocks cloud-IP ranges. Mitigation: route through a residential proxy if blocked; document the User-Agent contract clearly.
- **Multilingual gaps.** FinBERT is English-only. African bank reports are sometimes French. Mitigation: route French PDFs through a translation pre-pass *or* use a multilingual model (XLM-R fine-tuned on financial text). Decision deferred; prototype both.
- **Defamation / market-moving claims.** A misclassified theme on a regulated entity could be quoted in a research note and move a stock. Mitigation: never present scores without source sentences; banner on the UI clarifying the platform is a research aid, not investment advice.

## 8. Milestones

- **M1 (Week 1–2).** Multi-year ingestion + Parquet cache. Backfill latest 5 years for all 13 banks.
- **M2 (Week 3–4).** FinBERT classifier integrated alongside keyword scorer. Side-by-side scores in JSON output.
- **M3 (Week 5–6).** REST API with cached responses; OpenAPI schema published.
- **M4 (Week 7–8).** Web UI MVP with bank picker + theme dashboard.
- **M5 (Week 9).** Peer comparison heatmap, sentence-level evidence drawer.
- **M6 (Week 10).** Internal alpha with three pilot users; iterate.

## 9. Open questions

- Do we add Asian banks (Mizuho, MUFG, ICBC) in v2 or wait for v3? They file disclosures in TDnet/HKEX, not EDGAR — different parser path.
- Hosting: self-host the FinBERT inference (cheap, slower) or call a managed inference API (fast, $$$)? Decision needed before M2.
- Do we open-source the platform under MIT, or keep it private with a public-research demo? Affects everything from license to telemetry.
