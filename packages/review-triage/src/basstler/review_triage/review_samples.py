"""
The mechanical files left for review so a reviewer still sees, once, each new name a
pull request gives throughout.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.review_triage.comparison import FileSuffix, FileVerdict, MechanicalFile
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import Rename, RenameMap

# %% one sample


@dataclass(frozen=True)
class ReviewSample:
    """
    A mechanical file left for review because it shows a rename.
    """

    rename: Rename
    """
    The rename it shows.
    """

    path: PurePosixPath
    """
    The file, by its path in the head commit.
    """


# %% choosing the samples


@dataclass(frozen=True)
class ReviewSampling:
    """
    Picks one file showing each rename a reviewer judges and sees nowhere else: the file
    defining the new name where it is mechanical, otherwise the file using it most,
    reusing a file already picked where it shows the rename too.
    """

    def samples(
        self, renames: RenameMap, files: tuple[FileVerdict, ...]
    ) -> tuple[ReviewSample, ...]:
        """
        :param renames: The renames a pull request makes throughout.
        :param files: The verdict on each file it changes.
        :return: One sample for each rename no file needing review shows, in the order
            of the renames.
        """
        samples: list[ReviewSample] = []
        for rename in renames.identifier_renames:
            if rename.found_by.finds_moves:
                continue
            showing = [file for file in files if self.shows(file, rename)]
            mechanical = [file for file in showing if isinstance(file, MechanicalFile)]
            if not mechanical or len(mechanical) < len(showing):
                continue
            picked = self.pick(rename, mechanical, {each.path for each in samples})
            samples.append(ReviewSample(rename, picked))
        return tuple(samples)

    def pick(
        self,
        rename: Rename,
        files: list[MechanicalFile],
        picked: set[PurePosixPath],
    ) -> PurePosixPath:
        """
        :param rename: A rename.
        :param files: The mechanical files showing it.
        :param picked: The files already left for review as samples.
        :return: The file to show it in.
        """
        defining = sorted(
            file.change.path for file in files if rename.new in self.defined_names(file)
        )
        if defining:
            return next((path for path in defining if path in picked), defining[0])
        using = sorted(
            files,
            key=lambda file: (-self.uses(file, rename), file.change.path),
        )
        return next(
            (file.change.path for file in using if file.change.path in picked),
            using[0].change.path,
        )

    @staticmethod
    def shows(file: FileVerdict, rename: Rename) -> bool:
        """
        :param file: A changed file.
        :param rename: A rename.
        :return: Whether its base version uses the old name and its head version the
            new one.
        """
        old = re.compile(RenameMap.whole_word_pattern(rename))
        new = re.compile(rf"\b{re.escape(rename.new)}\b")
        return bool(
            old.search(file.change.base_text or "")
            and new.search(file.change.head_text or "")
        )

    @staticmethod
    def uses(file: FileVerdict, rename: Rename) -> int:
        """
        :param file: A changed file.
        :param rename: A rename.
        :return: How often its head version uses the new name.
        """
        return len(re.findall(rf"\b{re.escape(rename.new)}\b", file.change.head_text))

    @staticmethod
    def defined_names(file: FileVerdict) -> frozenset[str]:
        """
        :param file: A changed file.
        :return: The names its head version's functions, classes and assignments
            define, in the module and in its classes; none for a file of another type.
        """
        if file.change.path.suffix not in (FileSuffix.PYTHON, FileSuffix.PYTHON_STUB):
            return frozenset()
        tree = PythonSource(file.change.head_text).tree
        blocks = [tree.body] + [
            node.body for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        return frozenset().union(
            *(
                PythonSource.names_defined_by(statement)
                for block in blocks
                for statement in block
            )
        )
