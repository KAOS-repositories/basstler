"""
A GitHub repository given on the command line as ``owner/name``.
"""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter, Token

from basstler.github.repository import Repository

# %% converting the value


def parse_repository(_: type, tokens: tuple[Token, ...]) -> Repository:
    """
    Convert a command-line ``owner/name`` value.

    :param tokens: The one token given for the option.
    :return: The repository it names.
    :raises MalformedRepositoryError: If the value is not ``owner/name``.
    """
    return Repository.parse(tokens[0].value)


# %% the parameters

RepositoryArgument = Annotated[
    Repository,
    Parameter(converter=parse_repository, n_tokens=1, accepts_keys=False),
]
"""
An ``owner/name`` repository given on the command line.
"""

RepositoryOption = Annotated[
    Repository | None,
    Parameter(converter=parse_repository, n_tokens=1, accepts_keys=False),
]
"""
An optional ``owner/name`` repository given on the command line.
"""
