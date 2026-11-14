from __future__ import annotations


class ReviewMissing(Exception):
    """
    Raised when a pull request has no review.
    """
