"""
The rows an experiment produces, written as a Markdown table for people and as JSON for
later analysis.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from basstler.experiments.measurement import Measurement

ABSENT_VALUE = "—"
"""
What a cell shows where the experiment measured nothing.
"""

MARKDOWN_SUFFIX = ".md"
"""
The suffix of the table written for people.
"""

JSON_SUFFIX = ".json"
"""
The suffix of the rows written for later analysis.
"""


class ResultRow:
    """
    One row of an experiment's results; a subclass is a dataclass whose fields are the
    columns, in order.
    """


@dataclass(frozen=True)
class ResultTable:
    """
    The rows one experiment produced, all of one row class.
    """

    row_type: type[ResultRow]
    """
    The class of every row, whose fields are the columns.
    """

    rows: tuple[ResultRow, ...]
    """
    The rows, in the order they are shown.
    """

    def column_names(self) -> list[str]:
        """
        :return: The heading of each column.
        """
        return [
            column.name.replace("_", " ")
            for column in dataclasses.fields(self.row_type)
        ]

    @staticmethod
    def cell(value: object) -> str:
        """
        :param value: The value of one field of a row.
        :return: How the table shows it.
        """
        if value is None:
            return ABSENT_VALUE
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, float):
            return f"{value:.1f}"
        return str(value)

    def markdown(self) -> str:
        """
        :return: The rows as a Markdown table.
        """
        lines = [
            "| " + " | ".join(self.column_names()) + " |",
            "|" + "---|" * len(self.column_names()),
        ]
        lines.extend(
            "| "
            + " | ".join(
                self.cell(vars(row)[column.name]) for column in dataclasses.fields(row)
            )
            + " |"
            for row in self.rows
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def json_value(value: object) -> object:
        """
        :param value: The value of one field of a row.
        :return: It in a form :mod:`json` writes.
        """
        if isinstance(value, Measurement):
            return dataclasses.asdict(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return list(value)
        return value

    def json(self) -> str:
        """
        :return: The rows as a JSON list of objects keyed by field name.
        """
        return json.dumps(
            [
                {
                    column.name: self.json_value(vars(row)[column.name])
                    for column in dataclasses.fields(row)
                }
                for row in self.rows
            ],
            indent=1,
        )

    def write(self, directory: Path, name: str) -> tuple[Path, Path]:
        """
        Write the table and its rows next to each other.

        :param directory: The directory written into, created when missing.
        :param name: The name both files share.
        :return: The Markdown table and the JSON rows written.
        """
        directory.mkdir(parents=True, exist_ok=True)
        table = directory / f"{name}{MARKDOWN_SUFFIX}"
        rows = directory / f"{name}{JSON_SUFFIX}"
        table.write_text(self.markdown(), encoding="utf-8")
        rows.write_text(self.json(), encoding="utf-8")
        return table, rows
