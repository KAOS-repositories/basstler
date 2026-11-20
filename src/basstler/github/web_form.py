"""
A GitHub page whose fields its address fills in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from urllib.parse import quote, urlencode

# %% the fields


class UrlQueryParameter(StrEnum):
    """
    A query parameter a GitHub page fills one of its fields from; each form declares its
    own as members of a subclass.
    """


# %% the form


class PrefilledForm(ABC):
    """
    A GitHub page opened with its fields filled in from its address.
    """

    @property
    @abstractmethod
    def page_url(self) -> str:
        """
        The page's address without any field filled in.
        """

    @property
    @abstractmethod
    def filled_fields(self) -> Mapping[UrlQueryParameter, str]:
        """
        Each field the address fills in, with its value.
        """

    @property
    def url(self) -> str:
        """
        The page's address with every field of :attr:`filled_fields` filled in.
        """
        return self.url_filling(self.filled_fields)

    def url_filling(self, fields: Mapping[UrlQueryParameter, str]) -> str:
        """
        :param fields: The fields to fill in, with their values.
        :return: The page's address filling them in, each value percent-encoded.
        """
        return f"{self.page_url}?{urlencode(fields, quote_via=quote)}"
