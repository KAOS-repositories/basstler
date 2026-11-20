from __future__ import annotations


class RequestRefused(Exception):
    """
    Raised when a server refuses a request.
    """


class ReviewMissing(Exception):
    """
    Raised when a pull request has no review.
    """
