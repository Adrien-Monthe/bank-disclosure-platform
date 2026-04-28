"""
Command-line interface for the bank disclosure platform.

Examples
--------
    # Analyze JPMorgan's most recent 10-K:
    python -m src.cli analyze JPM

    # Analyze the latest 10-Q instead:
    python -m src.cli analyze BAC --quarterly

    # Analyze Afriland from a PDF URL (overrides the registry default):
    python -m src.cli analyze "Afriland" --pdf-url https://example.com/afriland_2024.pdf

    # List banks the platform tracks:
    python -m src.cli list
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .banks import BANKS
from .pipeline import analyze_bank, save_report


def cmd_list(_: argparse.Namespace) -> int:
    print(f"{'Bank':30s}  {'Ticker':8s}  {'Country':8s}  Source")
    print("-" * 70)
    for b in BANKS:
        print(f"{b.name:30s}  {(b.ticker or '—'):8s}  {b.country:8s}  {b.source.value}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    prefer = "quarterly" if args.quarterly else "annual"
    try:
        report = analyze_bank(
            args.identifier,
            prefer=prefer,
            pdf_url_override=args.pdf_url,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(report.to_json())

    if args.save:
        path = save_report(report)
        print(f"\nSaved to: {path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bank-disclosure",
        description="Parse and analyze bank disclosures (10-K/10-Q + PDF annual reports).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Show all tracked banks")
    p_list.set_defaults(func=cmd_list)

    p_analyze = sub.add_parser("analyze", help="Analyze a bank's latest disclosure")
    p_analyze.add_argument("identifier", help="Bank ticker or name (substring match)")
    p_analyze.add_argument("--quarterly", action="store_true",
                           help="Prefer 10-Q over 10-K when available")
    p_analyze.add_argument("--pdf-url", default=None,
                           help="Override registered PDF URL for this run")
    p_analyze.add_argument("--save", action="store_true",
                           help="Write report JSON to data/processed/")
    p_analyze.set_defaults(func=cmd_analyze)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
