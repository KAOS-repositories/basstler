"""
The names of the Actions secrets basstler's workflows read.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.github.repository import Repository

# %% a secret


class ActionsSecret(StrEnum):
    """
    The name of an Actions secret a workflow reads; each feature declares its own as
    members of a subclass.
    """

    def path_on(self, repository: Repository) -> str:
        """
        :param repository: The repository that stores it.
        :return: :meth:`Repository.actions_secret_path` of this secret there.
        """
        return repository.actions_secret_path(self)
