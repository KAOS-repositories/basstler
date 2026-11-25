from __future__ import annotations

from other_markers import called_positionally


@called_positionally
def on_message(message: str) -> None:
    print(message)
