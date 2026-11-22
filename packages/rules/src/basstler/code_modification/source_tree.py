"""
A snapshot of the files of a source tree, which actions change without touching disk.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

# %% the tree


@dataclass(frozen=True)
class SourceTree:
    """
    Every file of a tree and its content, by its path relative to the tree's root.
    """

    files: Mapping[Path, bytes]
    """
    The content of each file, by its path relative to the tree's root.
    """

    executable: frozenset[Path] = field(default_factory=frozenset)
    """
    The files of :attr:`files` that are executable.
    """

    @classmethod
    def read(cls, root: Path, paths: Iterable[Path]) -> SourceTree:
        """
        :param root: The directory the tree is read from.
        :param paths: The files to read, relative to *root*.
        :return: The tree of those files as *root* holds them.
        """
        paths = tuple(paths)
        return cls(
            {path: (root / path).read_bytes() for path in paths},
            frozenset(
                path for path in paths if (root / path).stat().st_mode & stat.S_IXUSR
            ),
        )

    @classmethod
    def of_directory(cls, root: Path) -> SourceTree:
        """
        :param root: A directory.
        :return: The tree of every file under *root*.
        """
        return cls.read(
            root,
            sorted(
                path.relative_to(root) for path in root.rglob("*") if path.is_file()
            ),
        )

    def with_files(
        self,
        added: Mapping[Path, bytes],
        removed: Iterable[Path] = (),
        executable: Iterable[Path] = (),
    ) -> SourceTree:
        """
        :param added: Files to add or overwrite, with their content.
        :param removed: Files to leave out.
        :param executable: The files of *added* that are executable; a file overwritten
            keeps whether it was.
        :return: This tree with *removed* left out and *added* in place.
        """
        removed_paths = set(removed)
        files = {
            path: content
            for path, content in self.files.items()
            if path not in removed_paths
        }
        return SourceTree(
            {**files, **added},
            (self.executable - removed_paths) | frozenset(executable),
        )

    def write(self, root: Path, previous: SourceTree) -> None:
        """
        Turn the files *previous* describes under *root* into this tree, removing every
        directory that leaves empty.

        :param root: The directory *previous* describes.
        :param previous: The tree *root* holds now.
        """
        for path in previous.files.keys() - self.files.keys():
            (root / path).unlink()
            for directory in (root / path).parents:
                if directory == root or any(directory.iterdir()):
                    break
                directory.rmdir()
        for path, content in self.files.items():
            if previous.files.get(path) != content:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_bytes(content)
            mode = (root / path).stat().st_mode
            executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            if path in self.executable:
                os.chmod(root / path, mode | executable_bits)
            else:
                os.chmod(root / path, mode & ~executable_bits)
