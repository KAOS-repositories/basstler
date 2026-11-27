from __future__ import annotations

from functools import wraps


def recorded(method):
    """
    Wraps *method*, skipping a call that passes any argument by keyword.
    """

    @wraps(method)
    def wrapper(self, *arguments, **options):
        if options:
            return None
        return method(self, *arguments, **options)

    return wrapper
