"""
The ordered path to a goal: its targets and everything they depend on across plans, with
what each step waits for and the action that carries it out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property
from graphlib import TopologicalSorter

from basstler.github.pull_request_source import PullRequestSource
from basstler.github.pull_request_state import LiveState
from basstler.github.repository import PullRequestReference, Repository
from basstler.json_model import ValidatedJSONModel
from basstler.plan.dependencies import (
    DependencyReference,
    PlanDirectory,
    ResolvedDependency,
)
from basstler.plan.exceptions import UnresolvedGoalReferenceError
from basstler.plan.goal import Goal
from basstler.plan.item_action import ItemAction
from basstler.plan.model import ItemStatus
from basstler.plan.model_alias import ModelAlias
from basstler.plan.structure import Item

# %% the report


class PathStepReport(ValidatedJSONModel):
    """
    One unfinished step of a path, as a command prints it.
    """

    reference: str
    """
    The step's item, as ``<plan-id>/<item-id>``.
    """

    title: str
    """
    The item's title.
    """

    status: ItemStatus
    """
    The status the item's plan records.
    """

    live_state: str
    """
    The item's pull request state on GitHub, as the plan site labels it.
    """

    pull_request_number: int | None
    """
    The item's pull request, if it has one.
    """

    recommended_model: ModelAlias | None
    """
    The model suited to the item, if one was recommended.
    """

    command: str | None
    """
    The command that carries the step out now, or ``None`` while it waits.
    """

    blockers: list[str]
    """
    What the item's plan records as blocking it.
    """

    awaited_merges: list[str]
    """
    The items the step cannot start before the merge of, each as ``<plan-id>/<item-id>``.
    """

    owner_move: str | None
    """
    What the item's pull request waits on the owner for, or ``None`` when nothing.
    """

    owner_commands: list[str]
    """
    The commands the owner runs to make that move, in order.
    """

    releases: list[str]
    """
    The steps that wait for this one, each as ``<plan-id>/<item-id>``.
    """


class PathGroupReport(ValidatedJSONModel):
    """
    The steps of a path that wait for the same items.
    """

    awaited: list[str]
    """
    The items the steps wait for, each as ``<plan-id>/<item-id>``; none for the steps
    that can be acted on now.
    """

    steps: list[PathStepReport]
    """
    The steps, in dependency order.
    """


class GoalPathReport(ValidatedJSONModel):
    """
    A goal's whole path, as a command prints it.
    """

    goal: Goal
    """
    The goal the path leads to.
    """

    next_command: str | None
    """
    The command of the first step that can be acted on, or ``None`` when none can.
    """

    groups: list[PathGroupReport]
    """
    The unfinished steps, the group that waits for nothing first.
    """

    finished: list[str]
    """
    The finished steps' items, each as ``<plan-id>/<item-id>``.
    """


# %% the owner's moves


class OwnerSituation(StrEnum):
    """
    What a step's pull request waits on the owner for; each value is the move, written
    around the pull request's number.
    """

    DRAFT_AWAITING_REVIEW = "review #{number} and mark it ready for review"
    """
    The pull request is a draft: only the owner moves it out of draft.
    """

    READY_TO_MERGE = "merge #{number}"
    """
    The pull request is out of draft: only the owner merges it.
    """


@dataclass(frozen=True, kw_only=True)
class OwnerMove(ABC):
    """
    The one thing a step waits on the owner for.
    """

    after: tuple[DependencyReference, ...] = ()
    """
    The steps that come before the owner's move.
    """

    @property
    @abstractmethod
    def summary(self) -> str:
        """
        The move, as a sentence fragment.
        """

    @property
    @abstractmethod
    def commands(self) -> tuple[str, ...]:
        """
        The commands the owner runs to make the move, in order.
        """

    @property
    @abstractmethod
    def waiting_phrase(self) -> str:
        """
        What the steps in :attr:`after` have to do first, as the words that follow their
        names.
        """

    @property
    def description(self) -> str:
        """
        The move as a sentence fragment, naming what it comes after.
        """
        if not self.after:
            return self.summary
        waited = ", ".join(reference.text for reference in self.after)
        return f"{self.summary} after {waited} {self.waiting_phrase}"


@dataclass(frozen=True, kw_only=True)
class PullRequestMove(OwnerMove):
    """
    What a step's pull request waits on the owner for.
    """

    situation: OwnerSituation
    """
    What the pull request waits for.
    """

    pull_request_number: int
    """
    The pull request the owner acts on.
    """

    @property
    def summary(self) -> str:
        return self.situation.format(number=self.pull_request_number)

    @property
    def commands(self) -> tuple[str, ...]:
        return ()

    @property
    def waiting_phrase(self) -> str:
        return "merges"


@dataclass(frozen=True, kw_only=True)
class OwnerPerformedStep(OwnerMove):
    """
    A step the owner carries out by hand.
    """

    title: str
    """
    The title of the item the owner performs.
    """

    step_commands: tuple[str, ...]
    """
    The commands the item's plan records for it, in order.
    """

    @property
    def summary(self) -> str:
        return self.title

    @property
    def commands(self) -> tuple[str, ...]:
        return self.step_commands

    @property
    def waiting_phrase(self) -> str:
        return "is ready"


# %% steps


@dataclass(frozen=True)
class PathStep:
    """
    One item on a goal's path.
    """

    resolved: ResolvedDependency
    """
    The item, the plan holding it and the reference the path names it by.
    """

    dependencies: tuple[DependencyReference, ...]
    """
    The steps this one depends on, in the order its plan writes them.
    """

    awaited: tuple[DependencyReference, ...]
    """
    The dependencies a not-started step still waits for: those not ready to build on.
    """

    action: ItemAction | None
    """
    What carries the step out now; ``None`` while it waits, and once it is finished.
    """

    owner_move: OwnerMove | None = None
    """
    What the step's pull request waits on the owner for, or ``None`` when nothing.
    """

    awaited_merges: tuple[DependencyReference, ...] = ()
    """
    The entries of :attr:`awaited` the step needs merged, not only out of draft.
    """

    @property
    def reference(self) -> DependencyReference:
        """
        The step's item, named with its plan.
        """
        return self.resolved.reference

    @property
    def item(self) -> Item:
        """
        The step's item.
        """
        return self.resolved.item

    @property
    def pull_request_reference(self) -> PullRequestReference | None:
        """
        The item's pull request in its plan's repository, if it has one.
        """
        if self.item.pull_request_number is None:
            return None
        return PullRequestReference(
            Repository.parse(self.resolved.repository), self.item.pull_request_number
        )

    @property
    def is_finished(self) -> bool:
        """
        Whether the item is done or its pull request has merged.
        """
        return self.item.is_effectively_done()

    def report(self, releases: tuple[DependencyReference, ...]) -> PathStepReport:
        """
        :param releases: The steps that wait for this one.
        :return: The step as a command prints it.
        """
        return PathStepReport(
            reference=self.reference.text,
            title=self.item.title,
            status=self.item.status,
            live_state=self.item.live_state.display_label,
            pull_request_number=self.item.pull_request_number,
            recommended_model=self.item.recommended_model,
            command=self.action.command if self.action else None,
            blockers=self.item.blockers,
            awaited_merges=[reference.text for reference in self.awaited_merges],
            owner_move=self.owner_move.description if self.owner_move else None,
            owner_commands=list(self.owner_move.commands) if self.owner_move else [],
            releases=[reference.text for reference in releases],
        )


@dataclass(frozen=True)
class PathGroup:
    """
    The unfinished steps of a path that wait for the same items.
    """

    awaited: tuple[DependencyReference, ...]
    """
    What every step of the group waits for; empty for the steps to act on now.
    """

    steps: tuple[PathStep, ...]
    """
    The steps, in dependency order.
    """

    @property
    def heading(self) -> str:
        """
        What the group is called in a printed path.
        """
        if not self.awaited:
            return "Now"
        return "After " + ", ".join(reference.text for reference in self.awaited)

    def report(self, path: GoalPath) -> PathGroupReport:
        """
        :param path: The path the group belongs to.
        :return: The group as a command prints it.
        """
        return PathGroupReport(
            awaited=[reference.text for reference in self.awaited],
            steps=[
                step.report(path.references_released_by(step)) for step in self.steps
            ],
        )


# %% the path


@dataclass(frozen=True)
class GoalPath:
    """
    Every step between the plans as they stand and a goal's targets.
    """

    goal: Goal
    """
    The goal the path leads to.
    """

    steps: tuple[PathStep, ...]
    """
    The targets and everything they depend on, each after the steps it depends on.
    """

    @classmethod
    def compute(
        cls,
        goal: Goal,
        plan_directory: PlanDirectory,
        pull_request_source: PullRequestSource,
    ) -> GoalPath:
        """
        :param goal: The goal to reach.
        :param plan_directory: The plans its targets and their dependencies live in.
        :param pull_request_source: Where the items' live state is read from.
        :raises UnresolvedGoalReferenceError: If a target or a dependency names no item.
        :raises graphlib.CycleError: If the dependencies form a cycle.
        :return: The path, with every item's live state classified.
        """
        needed = NeededItems.of_goal(goal, plan_directory)
        needed.refuse_unresolved_references()
        return cls.from_needed_items(needed, pull_request_source)

    @classmethod
    def from_needed_items(
        cls, needed: NeededItems, pull_request_source: PullRequestSource
    ) -> GoalPath:
        """
        :param needed: A goal's items, every reference among them resolved.
        :param pull_request_source: Where the items' live state is read from.
        :raises graphlib.CycleError: If the dependencies form a cycle.
        :return: The path, with every item's live state classified.
        """
        needed.classify_live_states(pull_request_source)
        steps: dict[DependencyReference, PathStep] = {}
        for reference in needed.in_dependency_order():
            steps[reference] = needed.step_of(reference)
        return cls(goal=needed.goal, steps=tuple(steps.values()))

    @cached_property
    def steps_by_reference(self) -> dict[DependencyReference, PathStep]:
        """
        Each of :attr:`steps`, by the reference naming its item.
        """
        return {step.reference: step for step in self.steps}

    @property
    def finished_steps(self) -> tuple[PathStep, ...]:
        """
        The steps whose items are done.
        """
        return tuple(step for step in self.steps if step.is_finished)

    @cached_property
    def groups(self) -> tuple[PathGroup, ...]:
        """
        The unfinished steps grouped by what they wait for, each group after the groups
        holding the steps it waits for.
        """
        distance: dict[DependencyReference, int] = {}
        grouped: dict[tuple[int, tuple[DependencyReference, ...]], list[PathStep]] = {}
        for step in self.steps:
            distance[step.reference] = 1 + max(
                (distance[awaited] for awaited in step.awaited), default=-1
            )
            if not step.is_finished:
                grouped.setdefault((distance[step.reference], step.awaited), []).append(
                    step
                )
        return tuple(
            PathGroup(awaited=awaited, steps=tuple(steps))
            for (_, awaited), steps in sorted(
                grouped.items(), key=lambda entry: entry[0][0]
            )
        )

    def references_released_by(self, step: PathStep) -> tuple[DependencyReference, ...]:
        """
        :param step: A step of the path.
        :return: The steps that wait for it, in path order.
        """
        return tuple(
            waiting.reference
            for waiting in self.steps
            if step.reference in waiting.awaited
        )

    @property
    def owner_steps(self) -> tuple[PathStep, ...]:
        """
        The steps whose pull requests the owner can act on now, in path order.
        """
        return tuple(
            step
            for step in self.steps
            if step.owner_move is not None and not step.owner_move.after
        )

    @property
    def next_step(self) -> PathStep | None:
        """
        The first step that can be acted on now, or ``None`` when none can.
        """
        return next(
            (
                step
                for group in self.groups
                for step in group.steps
                if step.action is not None
            ),
            None,
        )

    def report(self) -> GoalPathReport:
        """
        :return: The path as a command prints it.
        """
        next_step = self.next_step
        return GoalPathReport(
            goal=self.goal,
            next_command=next_step.action.command if next_step else None,
            groups=[group.report(self) for group in self.groups],
            finished=[step.reference.text for step in self.finished_steps],
        )

    def render(self) -> str:
        """
        :return: The path as text: the goal, the next command, then each group's steps.
        """
        report = self.report()
        lines = [
            f"Goal {self.goal.identifier}: {self.goal.title}",
            f"Next: {report.next_command or 'nothing can be acted on now'}",
        ]
        for group, group_report in zip(self.groups, report.groups, strict=True):
            lines += ["", group.heading]
            for step in group_report.steps:
                lines += self.step_lines(step)
        if report.finished:
            lines += ["", "Finished: " + ", ".join(report.finished)]
        return "\n".join(lines)

    @staticmethod
    def step_lines(step: PathStepReport) -> list[str]:
        """
        :param step: One reported step.
        :return: Its lines in a printed path: the item and its state, its title, its
            command and its blockers.
        """
        state = [step.status.value, step.live_state]
        if step.pull_request_number is not None:
            state.append(f"#{step.pull_request_number}")
        if step.recommended_model is not None:
            state.append(step.recommended_model.value)
        lines = [f"  {step.reference}  [{' · '.join(state)}]", f"      {step.title}"]
        if step.command is not None:
            lines.append(f"      {step.command}")
        if step.owner_move is not None:
            released = (
                f" (releases {', '.join(step.releases)})" if step.releases else ""
            )
            lines.append(f"      you: {step.owner_move}{released}")
        lines += [f"        {command}" for command in step.owner_commands]
        if step.awaited_merges:
            lines.append(f"      needs merged: {', '.join(step.awaited_merges)}")
        lines += [f"      blocked: {blocker}" for blocker in step.blockers]
        return lines


# %% the items a goal needs


@dataclass
class NeededItems:
    """
    A goal's targets and everything they depend on, resolved across plans.
    """

    goal: Goal
    """
    The goal whose items these are.
    """

    resolved_by_reference: dict[DependencyReference, ResolvedDependency]
    """
    Every needed item, by the reference naming it with its plan.
    """

    unresolved: list[UnresolvedGoalReferenceError] = field(default_factory=list)
    """
    The references among the targets and their dependencies that name no item.
    """

    @classmethod
    def of_goal(cls, goal: Goal, plan_directory: PlanDirectory) -> NeededItems:
        """
        :param goal: The goal to reach.
        :param plan_directory: The plans its items live in.
        :return: The targets and, transitively, everything they depend on that
            resolves, with the references that do not in :attr:`unresolved`.
        """
        needed = cls(goal=goal, resolved_by_reference={})
        pending = [
            (reference, "the goal's targets") for reference in goal.target_references
        ]
        while pending:
            reference, named_by = pending.pop()
            if reference in needed.resolved_by_reference:
                continue
            resolved = plan_directory.resolve(reference)
            if not isinstance(resolved, ResolvedDependency):
                needed.unresolved.append(
                    UnresolvedGoalReferenceError(
                        goal.identifier, reference.text, named_by
                    )
                )
                continue
            needed.resolved_by_reference[reference] = resolved
            pending += [
                (dependency, reference.text)
                for dependency in needed.dependencies_of(reference)
            ]
        return needed

    def refuse_unresolved_references(self) -> None:
        """
        :raises UnresolvedGoalReferenceError: If a target or a dependency names no item.
        """
        if self.unresolved:
            raise self.unresolved[0]

    def dependencies_of(
        self, reference: DependencyReference
    ) -> tuple[DependencyReference, ...]:
        """
        :param reference: A needed item.
        :return: What it depends on, each named with its plan.
        """
        resolved = self.resolved_by_reference[reference]
        return tuple(
            entry
            if entry.names_another_plan
            else DependencyReference(entry.item_identifier, resolved.plan.id)
            for entry in map(DependencyReference.from_text, resolved.item.depends_on)
        )

    def classify_live_states(self, pull_request_source: PullRequestSource) -> None:
        """
        Fill in the live GitHub state of every needed item.

        :param pull_request_source: Where the items' pull requests are read from.
        """
        live_pull_requests = pull_request_source.live_pull_requests_of(
            PullRequestReference(
                Repository.parse(resolved.repository),
                resolved.item.pull_request_number,
            )
            for resolved in self.resolved_by_reference.values()
            if resolved.item.pull_request_number is not None
        )
        for resolved in self.resolved_by_reference.values():
            resolved.classify_live_state(live_pull_requests)

    def in_dependency_order(self) -> list[DependencyReference]:
        """
        :raises graphlib.CycleError: If the dependencies form a cycle.
        :return: Every needed item, each after the items it depends on.
        """
        return list(
            TopologicalSorter(
                {
                    reference: self.dependencies_of(reference)
                    for reference in sorted(
                        self.resolved_by_reference, key=lambda entry: entry.text
                    )
                }
            ).static_order()
        )

    def step_of(self, reference: DependencyReference) -> PathStep:
        """
        :param reference: A needed item, its live state classified.
        :return: Its step: what it waits for and what carries it out.
        """
        resolved = self.resolved_by_reference[reference]
        dependencies = self.dependencies_of(reference)
        merged_dependencies = tuple(
            dependency
            for entry, dependency in zip(
                resolved.item.depends_on, dependencies, strict=True
            )
            if entry in resolved.item.depends_on_merged
        )
        awaited: tuple[DependencyReference, ...] = ()
        if resolved.item.status is ItemStatus.NOT_STARTED:
            awaited = tuple(
                dependency
                for dependency in dependencies
                if not self.resolved_by_reference[dependency].releases_dependent(
                    dependency in merged_dependencies
                )
            )
        action = None
        if not resolved.item.is_effectively_done():
            action = ItemAction.from_item_state(
                resolved.plan.id, resolved.item, dependencies_are_ready=not awaited
            )
        return PathStep(
            resolved=resolved,
            dependencies=dependencies,
            awaited=awaited,
            action=action,
            owner_move=self.owner_move_of(reference, awaited),
            awaited_merges=tuple(
                dependency
                for dependency in awaited
                if dependency in merged_dependencies
            ),
        )

    def owner_move_of(
        self, reference: DependencyReference, awaited: tuple[DependencyReference, ...]
    ) -> OwnerMove | None:
        """
        :param reference: A needed item, its live state classified.
        :param awaited: The dependencies the item still waits for.
        :return: What the item waits on the owner for, or ``None`` when nothing.
        """
        item = self.resolved_by_reference[reference].item
        if item.is_effectively_done():
            return None
        if item.is_performed_by_owner:
            return OwnerPerformedStep(
                title=item.title, step_commands=tuple(item.commands), after=awaited
            )
        if item.live_state is LiveState.OPEN_DRAFT:
            return PullRequestMove(
                situation=OwnerSituation.DRAFT_AWAITING_REVIEW,
                pull_request_number=item.pull_request_number,
            )
        if item.live_state is not LiveState.OPEN_READY:
            return None
        return PullRequestMove(
            situation=OwnerSituation.READY_TO_MERGE,
            pull_request_number=item.pull_request_number,
            after=tuple(
                dependency
                for dependency in self.dependencies_of(reference)
                if not self.resolved_by_reference[dependency].item.is_effectively_done()
            ),
        )
