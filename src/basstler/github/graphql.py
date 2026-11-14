"""
The shapes of GitHub's GraphQL API: the lists it returns, the mutations sent to it and
its answers to them.
"""

from __future__ import annotations

from typing import Annotated, Any, TypeVar

from basstler.class_property import classproperty
from basstler.github.client import GitHubWrite, HttpMethod
from basstler.github.exceptions import GraphQLMutationRefused
from basstler.json_model import RawValueReader, ValidatedJSONModel

# %% connections


class GraphQLNodes(RawValueReader):
    """
    Reads a GraphQL connection, which holds a list-valued field's entries under
    ``nodes``, as those entries.
    """

    def read(self, value: dict[str, Any] | list[Any]) -> list[Any]:
        if isinstance(value, list):
            return value
        return value["nodes"]


Node = TypeVar("Node")
"""
Whatever model the entries of a connection are parsed into.
"""

GraphQLConnection = Annotated[list[Node], GraphQLNodes()]
"""
A list-valued GraphQL field, which GitHub returns as a connection.
"""


# %% mutations


class GraphQLMutation(GitHubWrite):
    """
    One GraphQL mutation, sent to GitHub's GraphQL endpoint.
    """

    query: str
    """
    The mutation's document.
    """

    variables: dict[str, Any]
    """
    The document's variables.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.POST

    @property
    def path(self) -> str:
        return "graphql"


class GraphQLError(ValidatedJSONModel):
    """
    One error GitHub reports for a GraphQL request.
    """

    message: str
    """
    What went wrong.
    """


class GraphQLMutationAnswer(ValidatedJSONModel):
    """
    GitHub's answer to a GraphQL mutation, read only for its errors.
    """

    errors: tuple[GraphQLError, ...] = ()
    """
    The errors reported, none when the mutation succeeded.
    """

    def raise_if_refused(self) -> None:
        """
        :raises GraphQLMutationRefused: If GitHub reported errors.
        """
        if self.errors:
            raise GraphQLMutationRefused(tuple(error.message for error in self.errors))
