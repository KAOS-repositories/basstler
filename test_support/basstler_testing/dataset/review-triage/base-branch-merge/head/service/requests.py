from __future__ import annotations


def request(path):
    return path


class RequestRefused(Exception):
    """
    Raised when a server refuses a request.
    """
