"""
The board and its pieces.
"""


class Alpha:
    """
    The first piece.
    """

    def move(self) -> int:
        return 1


class Beta:
    """
    The second piece.
    """

    def move(self) -> int:
        return 2


def board_size() -> int:
    return 8
