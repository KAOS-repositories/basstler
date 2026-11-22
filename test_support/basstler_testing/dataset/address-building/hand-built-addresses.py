"""
Addresses appended to a repository's by hand, which the address check reports.
"""

from __future__ import annotations


def contents(repository, file_path):
    """
    :return: A REST path built by hand.
    """
    return f"{repository.api_path}/contents/{file_path}"


def settings(repository):
    """
    :return: A page built by hand.
    """
    return f"{repository.settings_url}/pages"
