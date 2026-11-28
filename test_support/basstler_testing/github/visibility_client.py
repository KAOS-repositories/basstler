"""
A stand-in for GitHub's REST API that says which repositories are private.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from basstler.github.repository import Repository

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.github.path_answering_client import PathAnsweringClient


def visibility_client(
    public: Iterable[Repository] = (), private: Iterable[Repository] = ()
) -> PathAnsweringClient:
    """
    :param public: The repositories that anybody can read.
    :param private: The repositories only their members can read.
    :return: A client that answers each of them with its resource, and refuses every
        other repository as not found.
    """
    public_resource = json.loads(
        DatasetLocation.REPOSITORY_NOT_FORK.read_text(encoding="utf-8")
    )
    private_resource = json.loads(
        DatasetLocation.REPOSITORY_PRIVATE.read_text(encoding="utf-8")
    )
    return PathAnsweringClient(
        answers={
            **{repository.api_path: public_resource for repository in public},
            **{repository.api_path: private_resource for repository in private},
        }
    )
