"""
The JSON each type checker reports its diagnostics in, read as far as the revealed types
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


# %% Pyrefly


class PyreflyError(ValidatedJSONModel):
    """
    One entry of Pyrefly's ``--output-format json`` report.
    """

    path: str
    """
    The file, relative to where Pyrefly ran.
    """

    line: int
    """
    The line, counted from one.
    """

    column: int
    """
    The column of the parenthesis before a revealed expression, counted from one, which
    is the expression's column counted from zero.
    """

    kind: Annotated[str, Field(alias="name")]
    """
    What the entry reports, ``reveal-type`` for a revealed type.
    """

    description: str
    """
    The entry's text, ``revealed type: ...`` for a revealed type.
    """


class PyreflyReport(ValidatedJSONModel):
    """
    Pyrefly's ``--output-format json`` report.
    """

    errors: tuple[PyreflyError, ...]
    """
    Every entry, revealed types among them.
    """
