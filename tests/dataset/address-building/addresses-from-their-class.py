"""
Addresses taken from the class that builds them, which the address check accepts.
"""

from __future__ import annotations


def contents(repository, file_path):
    """
    :return: The REST path the repository builds.
    """
    return repository.contents_path(file_path)


def label(repository):
    """
    :return: A repository's name inside a sentence, which is no address.
    """
    return f"{repository.full_name}/labels are listed"
