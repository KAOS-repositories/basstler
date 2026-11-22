"""
Prints, for each test identifier read from standard input as a JSON list, whether the
second of four suite shards holds it, as a JSON list.
"""

from __future__ import annotations

import json
import sys

from tests.suite_shard import SuiteShard


def print_holdings() -> None:
    """
    Read the identifiers and print whether the shard holds each.
    """
    shard = SuiteShard(index=1, count=4)
    print(json.dumps([shard.holds(identifier) for identifier in json.load(sys.stdin)]))


if __name__ == "__main__":
    print_holdings()
