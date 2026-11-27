from __future__ import annotations

from functools import wraps


def recorded(function):
    """
    Wraps *function*, requiring its first argument under a name of the wrapper's own.
    """

    @wraps(function)
    def wrapper(camera, *arguments, **options):
        return function(camera, *arguments, **options)

    return wrapper
