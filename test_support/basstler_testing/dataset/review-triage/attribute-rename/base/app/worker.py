"""
A thread measuring vectors.
"""

from __future__ import annotations

import threading


class Worker(threading.Thread):
    """
    Measures a vector when started, as the thread runs it with run.
    """

    def run(self) -> None:
        self.length = 1.0

    def measure(self) -> float:
        """
        :return: The length, measured now.
        """
        self.run()
        return self.length
