"""
Tests for :mod:`basstler.code_rules.address_building`: finding addresses appended to a
repository's by hand.
"""

from __future__ import annotations

from basstler.code_rules.address_building import HandBuiltAddressChecker
from basstler.locations import PackageLocation

from basstler_testing.constants.paths import AddressSnippet

# %% finding them


def reported_lines(path) -> list[int]:
    """
    :return: The first line of each hand-built address in *path*.
    """
    return [
        violation.first_line
        for violation in HandBuiltAddressChecker(
            package_directory=path.parent
        ).violations(path)
    ]


def test_a_path_or_page_appended_by_hand_is_reported():
    contents_line, settings_line = 12, 19
    assert reported_lines(AddressSnippet.HAND_BUILT) == [contents_line, settings_line]


def test_an_address_the_class_builds_is_not_reported():
    assert reported_lines(AddressSnippet.FROM_THEIR_CLASS) == []


def test_the_module_building_the_addresses_is_not_reported():
    assert reported_lines(PackageLocation.GITHUB_REPOSITORY_MODULE) == []


def test_a_source_outside_the_package_is_not_reported():
    assert list(HandBuiltAddressChecker().violations(AddressSnippet.HAND_BUILT)) == []
