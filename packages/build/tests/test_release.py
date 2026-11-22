"""
Tests for :mod:`basstler.build.release`: reading the files a build wrote.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest
from basstler.build.release import (
    BasstlerFamily,
    BuiltRelease,
    ReleaseFile,
    SourceDistribution,
    Wheel,
)

# %% the family


@pytest.mark.parametrize(
    ("distribution", "included"),
    [
        ("basstler", True),
        ("basstler-core", True),
        ("Basstler_Core", True),
        ("basstlerish", False),
        ("pyyaml", False),
    ],
)
def test_the_family_is_basstler_and_its_hyphenated_parts(
    distribution: str, included: bool
):
    """
    Each name beside whether it belongs to the family.
    """
    assert BasstlerFamily.includes(distribution) is included


# %% the built files

WHEEL_METADATA = (
    "Name: sample\nRequires-Dist: basstler-core==1.2.3\nRequires-Dist: pyyaml>=6\n"
)


def write_wheel(directory: Path) -> Path:
    """
    :param directory: Where to write.
    :return: A wheel of ``basstler-sample`` 1.2.3 carrying a licence and its metadata.
    """
    path = directory / "basstler_sample-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("basstler_sample-1.2.3.dist-info/METADATA", WHEEL_METADATA)
        archive.writestr("basstler_sample-1.2.3.dist-info/licenses/LICENSE", "licence")
    return path


def test_a_wheel_reads_its_name_version_and_requirements(tmp_path: Path):
    """
    The wheel's own name gives distribution and version; its metadata the requirements.
    """
    wheel = Wheel(write_wheel(tmp_path))

    assert wheel.distribution == "basstler-sample"
    assert wheel.version == "1.2.3"
    assert [str(requirement) for requirement in wheel.requirements] == [
        "basstler-core==1.2.3",
        "pyyaml>=6",
    ]


def test_a_wheel_returns_the_licence_file_it_carries(tmp_path: Path):
    """
    The bytes under ``dist-info/licenses`` come back.
    """
    wheel = Wheel(write_wheel(tmp_path))

    assert wheel.licence_file(ReleaseFile.LICENSE) == b"licence"


def test_a_source_distribution_carries_a_file_only_at_its_root(tmp_path: Path):
    """
    A file inside the archive but not at its root does not count.
    """
    root = "basstler_sample-1.2.3"
    path = tmp_path / f"{root}.tar.gz"
    carried = tmp_path / "LICENSE"
    carried.write_text("licence", encoding="utf-8")
    with tarfile.open(path, "w:gz") as archive:
        archive.add(carried, arcname=f"{root}/{ReleaseFile.LICENSE}")
        archive.add(carried, arcname=f"{root}/inner/{ReleaseFile.NOTICE}")

    source = SourceDistribution(path)

    assert source.distribution == "basstler-sample"
    assert source.carries_at_root(ReleaseFile.LICENSE)
    assert not source.carries_at_root(ReleaseFile.NOTICE)


def test_a_built_release_lists_both_kinds_by_distribution(tmp_path: Path):
    """
    Wheels and source distributions are each found by the distribution they are of.
    """
    write_wheel(tmp_path)
    (tmp_path / "basstler_sample-1.2.3.tar.gz").write_bytes(b"")

    release = BuiltRelease(tmp_path)

    assert set(release.wheels) == {"basstler-sample"}
    assert set(release.source_distributions) == {"basstler-sample"}
