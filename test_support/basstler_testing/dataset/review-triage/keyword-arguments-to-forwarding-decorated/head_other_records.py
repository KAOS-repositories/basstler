from __future__ import annotations

from functools import wraps


def recorded(method):
    """
    Wraps *method*, logging each call before passing its arguments on unchanged.
    """

    @wraps(method)
    def wrapper(self, *arguments, **options):
        if self.log is None:
            raise RuntimeError(method)
        self.log.append(method.__name__)
        result = method(self, *arguments, **options)
        self.log.append(result)
        return result

    return wrapper
