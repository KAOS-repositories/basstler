"""
A goal's page on the plan site, and its entry on its repository's index.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from basstler.class_property import classproperty
from basstler.locations import SiteTemplate
from basstler.plan.dependencies import DependencyReference
from basstler.plan.goal_path import GoalPath
from basstler.plan.model_alias import ModelAlias
from basstler.plan_site.plan_page_vocabulary import PlanPageVocabulary
from basstler.render_common import TemplatePage

# %% the goal's entry on the index


@dataclass(frozen=True)
class GoalSummary:
    """
    One goal on its repository's index: how far its path is, and what comes next.
    """

    title: str
    """
    The outcome the goal names.
    """

    page_url: str
    """
    The address of the goal's page.
    """

    finished_step_count: int
    """
    How many steps of the path are finished.
    """

    step_count: int
    """
    How many steps the path has.
    """

    next_move: str | None
    """
    What moves the first step that can be acted on, or ``None`` when none can.
    """

    @classmethod
    def from_path(cls, path: GoalPath, page_url: str) -> GoalSummary:
        """
        :param path: The goal's computed path.
        :param page_url: The address of the goal's page.
        :return: The goal's entry on the index.
        """
        next_step = path.next_step
        return cls(
            title=path.goal.title,
            page_url=page_url,
            finished_step_count=len(path.finished_steps),
            step_count=len(path.steps),
            next_move=next_step.next_move if next_step else None,
        )


# %% the goal's page


@dataclass
class GoalPage(TemplatePage):
    """
    One goal's page: the next step, then every unfinished step grouped by what it waits
    for, each linked to its item's card on its plan's page.
    """

    path: GoalPath
    """
    The goal's computed path.
    """

    repository_name: str
    """
    The repository whose notes hold the goal, as ``owner/repo``.
    """

    stylesheet_url: str
    """
    The address of the site's stylesheet.
    """

    hub_url: str
    """
    The hub's address, linked back up to.
    """

    index_url: str
    """
    The address of the repository's index, linked back up to.
    """

    locate_item_card: Callable[[DependencyReference], str]
    """
    Where a step's item has its card on its plan's page.
    """

    built_at: datetime
    """
    When the page is built.
    """

    @classproperty
    def template(cls) -> str:
        return SiteTemplate.GOAL.name

    @staticmethod
    def anchor_of(reference: DependencyReference) -> str:
        """
        :param reference: A step's item.
        :return: The ``id`` of that step on the page.
        """
        return f"step-{reference.plan_id}-{reference.item_identifier}"

    def render(self) -> str:
        """
        :return: The rendered HTML page.
        """
        return self.render_template(
            path=self.path,
            goal=self.path.goal,
            next_step=self.path.next_step,
            repository_name=self.repository_name,
            stylesheet_url=self.stylesheet_url,
            hub_url=self.hub_url,
            index_url=self.index_url,
            locate_item_card=self.locate_item_card,
            anchor_of=self.anchor_of,
            built_at=self.built_at,
            script_template=SiteTemplate.PLAN_SCRIPT.name,
            vocabulary=PlanPageVocabulary(),
            available_models=list(ModelAlias),
        )
