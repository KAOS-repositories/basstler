from __future__ import annotations

import functools


def called_positionally(method):
    """
    Wraps *method*.
    """
    return functools.wraps(method)(lambda *arguments: method(*arguments))
