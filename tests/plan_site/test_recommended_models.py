"""
Tests for :mod:`basstler.plan_site.recommended_models`: giving every item of every plan
on a notes branch the model it lacks.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import ProjectLocation
from basstler.plan.model import ManifestKey, PlanDocument, PlanManifest
from basstler.plan.model_alias import ModelAlias
from basstler.plan_site.recommended_models.every_plan import (
    RecommendedModelsInEveryPlan,
    RecommendedModelsLine,
)

from ..manifest_builders import manifest_item, minimal_plan

# %% every plan on a notes branch


def write_plan(root: Path, directory_name: str, **overrides: object) -> Path:
    """
    :param root: The root of a notes checkout.
    :param directory_name: The plan's directory name.
    :param overrides: Top-level keys of the plan to replace.
    :return: The plan's written manifest.
    """
    manifest_path = (
        root / ProjectLocation.PLANS / directory_name / PlanDocument.MANIFEST
    )
    manifest_path.parent.mkdir(parents=True)
    PlanManifest(minimal_plan(**overrides)).write(manifest_path)
    return manifest_path


def test_every_plan_gives_each_item_without_a_model_the_fallback(tmp_path: Path):
    items = [
        manifest_item("a", recommended_model=None),
        manifest_item("b", recommended_model=ModelAlias.OPUS.value),
    ]
    manifest_path = write_plan(tmp_path, "first", items=items)
    other_path = write_plan(
        tmp_path, "second", items=[manifest_item("c", recommended_model=None)]
    )

    RecommendedModelsInEveryPlan(fallback=ModelAlias.HAIKU).apply(tmp_path)

    key = ManifestKey.RECOMMENDED_MODEL.key
    assert [
        item.content[key] for item in PlanManifest.from_file(manifest_path).items
    ] == [ModelAlias.HAIKU.value, ModelAlias.OPUS.value]
    assert [item.content[key] for item in PlanManifest.from_file(other_path).items] == [
        ModelAlias.HAIKU.value
    ]


def test_every_plan_names_the_plans_it_changed(tmp_path: Path):
    write_plan(tmp_path, "first", items=[manifest_item("a", recommended_model=None)])
    write_plan(tmp_path, "second")
    edit = RecommendedModelsInEveryPlan()

    edit.apply(tmp_path)

    assert edit.summary.filled_plans == ["first"]
    assert edit.summary.line == RecommendedModelsLine.FILLED.format(plans="first")


def test_every_plan_leaves_complete_plans_alone(tmp_path: Path):
    manifest_path = write_plan(tmp_path, "first")
    before = manifest_path.read_text()
    edit = RecommendedModelsInEveryPlan()

    edit.apply(tmp_path)

    assert manifest_path.read_text() == before
    assert edit.summary.line == RecommendedModelsLine.NONE.value
