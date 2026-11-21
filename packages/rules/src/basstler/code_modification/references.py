"""
The matcher of a name that refers to a given object, however the file imports it.
"""

from __future__ import annotations

from dataclasses import dataclass

from libcst import matchers
from libcst.metadata import QualifiedName, QualifiedNameProvider

# %% the reference


@dataclass(frozen=True)
class ReferenceTo:
    """
    A name or attribute that refers to a module, or to something in it, through the
    imports of the file it is in.
    """

    qualified_name: str
    """
    The dotted name of the module, function or class referred to, as ``shutil.rmtree``.
    """

    @property
    def matcher(self) -> matchers.MatchMetadataIfTrue:
        """
        The matcher a name or attribute satisfies when it refers to
        :attr:`qualified_name` or to a member of it; a pattern using it is found with
        the metadata of its module.
        """
        return matchers.MatchMetadataIfTrue(QualifiedNameProvider, self.is_referred_to)

    def is_referred_to(self, names: set[QualifiedName]) -> bool:
        """
        :param names: The qualified names a node refers to.
        :return: Whether one of them is :attr:`qualified_name` or a member of it.
        """
        return any(
            name.name == self.qualified_name
            or name.name.startswith(f"{self.qualified_name}.")
            for name in names
        )
