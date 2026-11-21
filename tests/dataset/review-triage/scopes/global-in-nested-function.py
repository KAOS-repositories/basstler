from __future__ import annotations


def configure():
    def enable():
        if True:
            global enabled  # noqa: PLW0603
            enabled = True

    return lambda: [step for step in range(3)]
