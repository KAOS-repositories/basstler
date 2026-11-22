"""
The git objects GitHub's REST resources name by their hash, and the file content they
carry encoded.
"""

from __future__ import annotations

import base64
from typing import Annotated

from pydantic import Field

from basstler.json_model import ValidatedJSONModel

# %% objects


class GitObject(ValidatedJSONModel):
    """
    A resource standing for one git object - a commit, a blob - which GitHub names by
    its hash.
    """

    object_hash: Annotated[str, Field(alias="sha")]
    """
    The git object's hash.
    """


# %% content


class EncodedContent(ValidatedJSONModel):
    """
    A resource carrying a file's content, base64-encoded as the contents API reads and
    writes it.
    """

    content: str
    """
    The file's content, base64-encoded, with line breaks where GitHub returns it.
    """

    @property
    def text(self) -> str:
        """
        The file's content, decoded.
        """
        return base64.b64decode(self.content).decode()

    @staticmethod
    def encode(text: str) -> str:
        """
        :param text: A file's whole content.
        :return: *text*, base64-encoded as the contents API takes it.
        """
        return base64.b64encode(text.encode()).decode()
