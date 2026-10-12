import pytest
from app import paginate

def test_pagination_boundary():
    items = list(range(100))
    # Page 1 of size 10 must return 10 elements [0..9]
    page_1 = paginate(items, page=1, size=10)
    assert len(page_1) == 10, f"Expected 10 items, but got {len(page_1)}"
    assert page_1 == list(range(10))

def test_pagination_second_page():
    items = list(range(100))
    page_2 = paginate(items, page=2, size=10)
    assert len(page_2) == 10
    assert page_2 == list(range(10, 20))
