"""
Tests for the measurements, result tables and tool installations every experiment
reuses.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from basstler.experiments.measurement import BYTES_PER_MEGABYTE, Measurement, Unit
from basstler.experiments.results import (
    ABSENT_VALUE,
    JSON_SUFFIX,
    MARKDOWN_SUFFIX,
    ResultRow,
    ResultTable,
)
from basstler.experiments.tool_installation import InstallFootprint, ToolInstallation

# %% measurements


def test_a_measurement_summarises_its_samples():
    """
    A measurement holds the mean and sample standard deviation of its samples.
    """
    samples = [1.0, 2.0, 4.0]

    measurement = Measurement.from_samples(samples, Unit.SECONDS)

    assert measurement == Measurement(
        statistics.mean(samples), statistics.stdev(samples), Unit.SECONDS, len(samples)
    )


def test_a_single_sample_has_no_spread():
    """
    One sample has a standard deviation of zero, and is shown without one.
    """
    measurement = Measurement.from_samples([3.0], Unit.SECONDS)

    assert (measurement.standard_deviation, str(measurement)) == (0.0, "3.0 s")


# %% result tables


@dataclass(frozen=True)
class MeasuredRow(ResultRow):
    """
    A row of a name, a count, a measurement and a value not measured.
    """

    name: str
    """
    What was measured.
    """

    count: int
    """
    How many were found.
    """

    seconds: Measurement
    """
    How long it took.
    """

    size: float | None
    """
    Not measured.
    """


ROW = MeasuredRow("first", 3, Measurement(1.5, 0.5, Unit.SECONDS, 2), None)
"""
The row the table tests write.
"""


def test_a_table_shows_each_field_as_a_column():
    """
    The Markdown table has a column per field and shows an absent value as such.
    """
    table = ResultTable((ROW,))

    assert table.markdown().splitlines() == [
        "| name | count | seconds | size |",
        "|---|---|---|---|",
        f"| first | 3 | {ROW.seconds} | {ABSENT_VALUE} |",
    ]


def test_a_table_is_written_for_people_and_for_analysis(tmp_path: Path):
    """
    Writing a table writes the Markdown table and the rows as JSON under one name.
    """
    table = ResultTable((ROW,))

    written = table.write(tmp_path, "measured")

    assert written == (
        tmp_path / f"measured{MARKDOWN_SUFFIX}",
        tmp_path / f"measured{JSON_SUFFIX}",
    )
    assert json.loads(written[1].read_text(encoding="utf-8")) == [
        {
            "name": ROW.name,
            "count": ROW.count,
            "seconds": {
                "mean": ROW.seconds.mean,
                "standard_deviation": ROW.seconds.standard_deviation,
                "unit": ROW.seconds.unit.value,
                "repetitions": ROW.seconds.repetitions,
            },
            "size": None,
        }
    ]


# %% tool installations


def installed_distribution(
    site_packages: Path, name: str, version: str, module_bytes: int
) -> None:
    """
    Record a distribution installing one module of a given size.

    :param site_packages: The environment's ``site-packages``.
    :param name: The distribution's name.
    :param version: Its version.
    :param module_bytes: The size of its one module.
    """
    record = site_packages / f"{name}-{version}.dist-info"
    record.mkdir(parents=True)
    (record / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
    )
    (record / "RECORD").write_text(f"{name}.py,,\n", encoding="utf-8")
    (site_packages / f"{name}.py").write_bytes(b"#" * module_bytes)


def test_a_footprint_counts_the_tool_its_dependencies_and_its_downloads(
    tmp_path: Path,
):
    """
    The footprint adds up the files the tool, its dependencies and its first run's
    downloads take, leaving out the installer the environment starts with.
    """
    site_packages = tmp_path / "Lib" / "site-packages"
    installed_distribution(site_packages, "checker", "1.0", 1000)
    installed_distribution(site_packages, "helper", "2.0", 500)
    installed_distribution(site_packages, "pip", "25.0", 7000)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "server.js").write_bytes(b"#" * 250)
    installation = ToolInstallation("checker", tmp_path, downloads=(downloads,))

    assert installation.footprint() == InstallFootprint(
        "1.0", (1000 + 500 + 250) / BYTES_PER_MEGABYTE, ("helper",)
    )
