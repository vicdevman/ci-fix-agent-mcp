"""Pagination helpers for list endpoints."""

import math


def paginate(items, page, per_page=10):
    """Return the items for a 1-indexed page number."""
    if page < 1:
        raise ValueError("page must be 1 or greater")
    if per_page < 1:
        raise ValueError("per_page must be 1 or greater")

    start = page * per_page
    end = start + per_page
    return items[start:end]


def total_pages(items, per_page=10):
    """Return how many pages are needed to show every item."""
    if per_page < 1:
        raise ValueError("per_page must be 1 or greater")
    return max(1, math.ceil(len(items) / per_page))
