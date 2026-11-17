"""
The JSON mypy and pyright report their diagnostics in, read as far as the revealed types
need.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from basstler.json_model import ValidatedJSONModel

# %% mypy


class MypyDiagnostic(ValidatedJSONModel):
    """
    One line of mypy's ``--output json``: a diagnostic, such as a revealed type's note.
    """

    file: str
    """
    The file, relative to where mypy ran.
    """

    line: int
    """
    The line, counted from one.
    """

    column: int
    """
    The column of the expression, counted from zero.
    """

    message: str
    """
    The diagnostic's text, ``Revealed type is "..."`` for a revealed type.
    """


# %% pyright


class PyrightPosition(ValidatedJSONModel):
    """
    A position in a file as pyright reports it.
    """

    line: int
    """
    The line, counted from zero.
    """

    character: int
    """
    The column, counted from zero.
    """


class PyrightRange(ValidatedJSONModel):
    """
    The span of source a pyright diagnostic is about.
    """

    start: PyrightPosition
    """
    Where the span starts.
    """


class PyrightDiagnostic(ValidatedJSONModel):
    """
    One diagnostic of pyright's ``--outputjson`` report.
    """

    file: str
    """
    The file's absolute path.
    """

    message: str
    """
    The diagnostic's text, ``Type of "..." is "..."`` for a revealed type.
    """

    range: PyrightRange
    """
    The span of the expression it is about.
    """


class PyrightReport(ValidatedJSONModel):
    """
    pyright's ``--outputjson`` report.
    """

    diagnostics: Annotated[
        tuple[PyrightDiagnostic, ...], Field(alias="generalDiagnostics")
    ]
    """
    Every diagnostic, revealed types among them.
    """
