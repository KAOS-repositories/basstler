"""
The ordered path to a goal: its targets and everything they depend on across plans, with
what each step waits for and the action that carries it out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from graphlib import TopologicalSorter

from basstler.github.pull_request_source import PullRequestSource
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

    def report(self) -> PathStepReport:
        """
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

    def report(self) -> PathGroupReport:
        """
        :return: The group as a command prints it.
        """
        return PathGroupReport(
            awaited=[reference.text for reference in self.awaited],
            steps=[step.report() for step in self.steps],
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
            groups=[group.report() for group in self.groups],
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
        awaited: tuple[DependencyReference, ...] = ()
        if resolved.item.status is ItemStatus.NOT_STARTED:
            awaited = tuple(
                dependency
                for dependency in dependencies
                if not self.resolved_by_reference[
                    dependency
                ].is_ready_to_unblock_dependents()
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
        )
