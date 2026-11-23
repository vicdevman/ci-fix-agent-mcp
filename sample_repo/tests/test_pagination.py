import pytest

from pagination import paginate, total_pages

ITEMS = list(range(1, 26))  # 25 items: 1..25


def test_first_page_starts_at_first_item():
    assert paginate(ITEMS, page=1, per_page=10) == list(range(1, 11))


def test_second_page():
    assert paginate(ITEMS, page=2, per_page=10) == list(range(11, 21))


def test_last_page_is_partial():
    assert paginate(ITEMS, page=3, per_page=10) == [21, 22, 23, 24, 25]


def test_page_past_the_end_is_empty():
    assert paginate(ITEMS, page=4, per_page=10) == []


def test_invalid_page_raises():
    with pytest.raises(ValueError):
        paginate(ITEMS, page=0)


def test_total_pages_rounds_up():
    assert total_pages(ITEMS, per_page=10) == 3


def test_total_pages_for_empty_list():
    assert total_pages([], per_page=10) == 1
