"""
Removing a directory and everything in it, read-only entries included.
"""

from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# %% the tree


@dataclass(frozen=True)
class DirectoryTree:
    """
    A directory and everything in it, such as a clone whose object files git left
    read-only, which Windows refuses to delete.
    """

    root: Path
    """
    The directory at the top of the tree.
    """

    ignore_errors: bool = False
    """
    Whether an entry that refuses removal for a reason other than being read-only is
    left in place instead of raising.
    """

    def remove(self) -> None:
        """
        Delete the tree, making each entry that refuses deletion writable first; a tree
        that is not there is left as it is.
        """
        if not self.root.exists():
            return
        shutil.rmtree(self.root, onexc=self.handle_refusal)

    def handle_refusal(
        self, removal: Callable[[str], object], path: str, refusal: BaseException
    ) -> None:
        """
        Make *path* and the directory holding it writable, then remove it again.

        :param removal: The function that refused to remove *path*.
        :param path: The entry it refused.
        :param refusal: Why it refused; raised again unless it is a permission error or
            :attr:`ignore_errors` is set.
        """
        if not isinstance(refusal, PermissionError):
            if self.ignore_errors:
                return
            raise refusal
        writable = stat.S_IRWXU
        os.chmod(os.path.dirname(path), writable)
        os.chmod(path, writable)
        removal(path)
