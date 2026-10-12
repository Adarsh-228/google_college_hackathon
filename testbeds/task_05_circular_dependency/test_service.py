import pytest
from service import get_checkout_price

def test_vip_discount():
    total = get_checkout_price(100.0, is_vip=True)
    assert total == 90.0, f"Expected 90.0 for VIP, got {total}"

def test_regular_price():
    total = get_checkout_price(100.0, is_vip=False)
    assert total == 100.0
