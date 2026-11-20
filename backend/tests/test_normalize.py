"""Tests for the deterministic normalization layer."""
from app.normalize import REFERENCE_FX_RATES, normalize_amount, normalize_currency, normalize_vendor_name


def test_vendor_name_variants_collapse():
    assert normalize_vendor_name("SUNBEAM ELECTRICALS PVT. LTD.") == \
        normalize_vendor_name("Sunbeam Electricals Pvt Ltd")
    assert normalize_vendor_name("SUNBEAM ELECTRICALS PVT. LTD.") == "SUNBEAM ELECTRICALS"


def test_currency_symbols_map_to_iso():
    assert normalize_currency("₹") == "INR"
    assert normalize_currency("Rs.") == "INR"
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("$") == "USD"


def test_amounts_survive_formatting_noise():
    assert normalize_amount("Rs. 4,956.00") == 4956.0
    assert normalize_amount("₹17,016.00") == 17016.0
    assert normalize_amount("garbage") == 0.0


def test_reference_fx_rates_present_for_r4():
    assert REFERENCE_FX_RATES["USD"] > 0
    assert REFERENCE_FX_RATES["EUR"] > 0
    assert REFERENCE_FX_RATES["INR"] == 1.0
