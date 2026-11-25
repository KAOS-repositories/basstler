from __future__ import annotations


def called_positionally(method):
    """
    Wraps *method*, passing its arguments on reversed.
    """

    def wrapper(*arguments):
        return method(*reversed(arguments))

    return wrapper
