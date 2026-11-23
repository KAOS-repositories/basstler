"""
Tests for the patterns the notes tooling reads text with: the names a document cites, a
personal ``stack.toml``'s upstream line, and a requirement's distribution name.
"""

from __future__ import annotations

import pytest

from basstler.document_references import CitedNames
from basstler.github.stack_configuration import StackSetting
from basstler.setup.dependencies import Dependency
from basstler.setup.steps import PersonalUpstream

# %% the names a document cites


@pytest.mark.parametrize(
    ("text", "modules", "skills"),
    [
        ("basstler.plan_manifest_tools", {"plan_manifest_tools"}, set()),
        ("basstler.plan.model.PlanDocument", {"plan.model"}, set()),
        ("src/basstler/plan_size_limits.py", {"plan_size_limits"}, set()),
        ('"basstler.sh" plan_manifest_tools --help', {"plan_manifest_tools"}, set()),
        (
            '"${BASSTLER_PLUGIN_ROOT}/hooks/basstler.sh" plan.item_mode',
            {"plan.item_mode"},
            set(),
        ),
        ("`basstler.sh maintenance push`", {"maintenance"}, set()),
        ("run /plan-create first", set(), {"plan-create"}),
        ("the basstler.sh script", set(), set()),
        ("basstler.sh", set(), set()),
        ("https://example.com/plan-create", set(), set()),
        ("a/b/plan-create and not-basstler.plan", set(), set()),
        ("/plan", set(), set()),
    ],
)
def test_the_modules_and_skills_a_document_cites_are_read_from_its_text(
    text: str, modules: set[str], skills: set[str]
):
    """
    Each text is listed beside the modules and the skills cited in it.
    """
    cited = CitedNames.in_text(text)

    assert (set(cited.modules), set(cited.skills)) == (modules, skills)


# %% the upstream line of a personal stack.toml


@pytest.mark.parametrize(
    ("line", "is_the_setting"),
    [
        (f'{StackSetting.UPSTREAM_REPOSITORY} = "owner/repo"', True),
        (f'  {StackSetting.UPSTREAM_REPOSITORY}="owner/repo"', True),
        (f'\t{StackSetting.UPSTREAM_REPOSITORY} = "owner/repo"  ', True),
        (f'# {StackSetting.UPSTREAM_REPOSITORY} = "owner/repo"', False),
        (f'{StackSetting.UPSTREAM_REPOSITORY}_other = "owner/repo"', False),
        (f'{StackSetting.IN_REVIEW_LABEL} = "in-review"', False),
        ("", False),
    ],
)
def test_the_line_naming_the_upstream_is_the_only_one_found(
    line: str, is_the_setting: bool
):
    """
    Each line is listed beside whether it names the upstream.
    """
    assert (PersonalUpstream.setting_line.search(line) is not None) is is_the_setting


# %% the name of a required distribution


@pytest.mark.parametrize(
    ("specifier", "name"),
    [
        ("pydantic>=2", "pydantic"),
        ("basstler-core[extra]>=1.0", "basstler-core"),
        ("typing-extensions ; python_version<'3.13'", "typing-extensions"),
        ("plain", "plain"),
    ],
)
def test_the_name_of_a_required_distribution_stops_at_its_constraints(
    specifier: str, name: str
):
    """
    Each specifier is listed beside the distribution name read from it.
    """
    assert Dependency(specifier).distribution_name == name
