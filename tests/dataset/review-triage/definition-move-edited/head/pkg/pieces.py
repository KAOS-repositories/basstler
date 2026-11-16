"""
The pieces that move on the board.
"""

# %% pieces


class Alpha:
    """
    The first piece to move.
    """

    def move(self) -> int:
        return 1


class Beta:
    """
    The second piece.
    """

    def move(self) -> int:
        return 2
