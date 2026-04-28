"""Tests for the bank registry."""

import pytest

from src.banks import BANKS, SourceType, banks_by_source, get_bank


def test_registry_includes_african_and_global():
    countries = {b.country for b in BANKS}
    # Spec required African + Global mix
    assert "US" in countries
    assert "CM" in countries  # Afriland (Cameroon)
    assert "ZA" in countries  # Standard Bank (South Africa)


def test_get_bank_by_ticker():
    bank = get_bank("JPM")
    assert bank.name == "JPMorgan Chase"
    assert bank.cik == "0000019617"


def test_get_bank_by_name_substring():
    bank = get_bank("afriland")
    assert "Afriland" in bank.name
    assert bank.source == SourceType.ANNUAL_REPORT_PDF


def test_get_bank_case_insensitive():
    assert get_bank("jpm").name == "JPMorgan Chase"
    assert get_bank("JPM").name == "JPMorgan Chase"


def test_get_bank_raises_on_unknown():
    with pytest.raises(KeyError):
        get_bank("not-a-real-bank-12345")


def test_edgar_banks_have_cik():
    for bank in banks_by_source(SourceType.SEC_EDGAR):
        assert bank.cik, f"{bank.name} is SEC_EDGAR but has no CIK"
        assert len(bank.cik) == 10, f"{bank.name} CIK should be 10-digit padded"


def test_pdf_banks_have_url():
    for bank in banks_by_source(SourceType.ANNUAL_REPORT_PDF):
        assert bank.annual_report_url, f"{bank.name} is PDF but has no URL"
