"""
Handing plans over to another person: the plans, their items' progress notes and the
repository's rules, read off one personal-notes branch, written out with a guide to
working every item, and saved onto another personal-notes branch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath

import rustworkx

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.github.repository import Repository
from basstler.locations import PlanHandoverLocation, ProjectLocation
from basstler.personal_notes.branch import NotesBranchWriter, NotesFileChanges
from basstler.personal_notes.progress_notes import ProgressNotesFile
from basstler.plan.dependencies import DependencyReference
from basstler.plan.exceptions import (
    HandoverPlanCycleError,
    PlanAlreadyTrackedError,
    PlanOutsideHandoverError,
    PlanStillNamedError,
)
from basstler.plan.item_bootstrap.documents import (
    PlanDocuments,
    PlanSaveScript,
    ProjectCheckout,
)
from basstler.plan.merge import PlanVersion
from basstler.plan.model import ItemStatus, ManifestKey, PlanDocument, PlanManifest
from basstler.plan.repository_rules import RepositoryRules
from basstler.plan.repository_rules_store import RepositoryRulesStore
from basstler.plan.size_limits import Roadmap
from basstler.render_common import TemplatePage
from basstler.shell_configuration import FetchedBranchReference

# %% one handed-over plan


@dataclass(frozen=True)
class HandoverPlan:
    """
    One plan as it is handed over.
    """

    manifest: PlanManifest
    """
    The plan's manifest.
    """

    roadmap_text: str
    """
    The plan's standing rules, as its roadmap holds them.
    """

    @property
    def identifier(self) -> str:
        """
        The plan's id.
        """
        return self.manifest.identifier

    @property
    def version(self) -> PlanVersion:
        """
        Both documents, as a save writes them.
        """
        return PlanVersion(
            manifest_text=self.manifest.text, roadmap_text=self.roadmap_text
        )

    @property
    def standing_rules(self) -> list[str]:
        """
        The rules the roadmap holds, one entry each.
        """
        return Roadmap.from_text(self.roadmap_text).entries

    @property
    def depended_on_plans(self) -> set[str]:
        """
        The ids of the other plans whose items this plan's items depend on.
        """
        return DependencyReference.read_other_plans(
            plan_identifier=self.identifier,
            entries=(
                dependency
                for item in self.manifest.items
                for dependency in item.dependencies
            ),
        )

    def without_sessions(self) -> HandoverPlan:
        """
        :return: This plan with no item naming a session, since only the person who ran
            a session can open it.
        """
        items = [
            {
                key: value
                for key, value in item.content.items()
                if key != ManifestKey.SESSION.key
            }
            for item in self.manifest.items
        ]
        return HandoverPlan(
            manifest=PlanManifest(
                {**self.manifest.content, ManifestKey.ITEMS.key: items}
            ),
            roadmap_text=self.roadmap_text,
        )

    def moved_to_repository(self, repository: Repository) -> HandoverPlan:
        """
        :param repository: The repository the receiver's checkout is a clone of.
        :return: This plan with *repository* as its default, every item that already
            has a branch or pull request kept on the repository it is on, and no
            tracking issue, whose number named one of the old default's issues; the plan
            itself when *repository* is its default already.
        """
        if repository == self.manifest.default_repository:
            return self
        items = [
            {
                **item.content,
                ManifestKey.REPOSITORY.key: self.manifest.repository_of(item).full_name,
            }
            if item.branch or item.pull_request_number is not None
            else item.content
            for item in self.manifest.items
        ]
        content = {
            key: value
            for key, value in self.manifest.content.items()
            if key != ManifestKey.TRACKING_ISSUE.key
        }
        return HandoverPlan(
            manifest=PlanManifest(
                {
                    **content,
                    ManifestKey.DEFAULT_REPOSITORY.key: repository.full_name,
                    ManifestKey.ITEMS.key: items,
                }
            ),
            roadmap_text=self.roadmap_text,
        )

    def with_pull_requests(self, numbers: Mapping[str, int]) -> HandoverPlan:
        """
        :param numbers: A pull request on the plan's default repository for some of its
            items, by item id.
        :return: This plan with each of those items naming its pull request there.
        """
        items = [
            {
                **{
                    key: value
                    for key, value in item.content.items()
                    if key != ManifestKey.REPOSITORY.key
                },
                ManifestKey.PULL_REQUEST_NUMBER.key: numbers[item.identifier],
            }
            if item.identifier in numbers
            else item.content
            for item in self.manifest.items
        ]
        return HandoverPlan(
            manifest=PlanManifest(
                {**self.manifest.content, ManifestKey.ITEMS.key: items}
            ),
            roadmap_text=self.roadmap_text,
        )

    def item_anchor(self, *, reference_text: str) -> str:
        """
        :param reference_text: An item's id, or a ``depends_on`` entry of this plan.
        :return: The anchor of that item's section in the guide.
        """
        reference = DependencyReference.from_text(reference_text)
        return f"{reference.plan_id or self.identifier}--{reference.item_identifier}"


# %% the handover


@dataclass(frozen=True)
class PlanHandover:
    """
    Plans handed over together, with what their items' work needs beyond the plans.

    Every plan an item depends on is among them, and they depend on each other without a
    cycle, so the receiver can save each one after the plans it names.
    """

    plans: tuple[HandoverPlan, ...]
    """
    The handed-over plans.
    """

    progress_notes: Mapping[str, str]
    """
    The progress note of each handed-over item's branch that has one, by branch.
    """

    repository_rules: RepositoryRules
    """
    The rules every plan of the repository follows.
    """

    def __post_init__(self) -> None:
        """
        :raises PlanOutsideHandoverError: If a plan depends on a plan left out.
        :raises HandoverPlanCycleError: If the plans depend on each other in a cycle.
        """
        identifiers = {plan.identifier for plan in self.plans}
        for plan in self.plans:
            missing = plan.depended_on_plans - identifiers
            if missing:
                raise PlanOutsideHandoverError(
                    plan_identifier=plan.identifier,
                    missing_plan_identifiers=tuple(sorted(missing)),
                )
        if not rustworkx.is_directed_acyclic_graph(self.plan_dependency_graph):
            raise HandoverPlanCycleError(
                plan_identifiers=tuple(plan.identifier for plan in self.plans)
            )

    @cached_property
    def plan_dependency_graph(self) -> rustworkx.PyDiGraph:
        """
        The plans, each with an edge to every plan that depends on it.
        """
        graph = rustworkx.PyDiGraph()
        nodes = {plan.identifier: graph.add_node(plan) for plan in self.plans}
        for plan in self.plans:
            for depended_on in plan.depended_on_plans:
                graph.add_edge(nodes[depended_on], nodes[plan.identifier], None)
        return graph

    @property
    def plans_in_saving_order(self) -> list[HandoverPlan]:
        """
        The plans, each after every plan it depends on, otherwise by id.
        """
        return list(
            rustworkx.lexicographical_topological_sort(
                self.plan_dependency_graph, key=lambda plan: plan.identifier
            )
        )

    @staticmethod
    def progress_note_path(branch: str) -> PurePosixPath:
        """
        :param branch: A branch.
        :return: Where its progress note is, relative to a progress-notes directory.
        """
        return PurePosixPath(f"{branch}{ProgressNotesFile.SUFFIX}")

    @classmethod
    def from_notes_branch(
        cls, *, project_root: Path, plan_identifiers: list[str]
    ) -> PlanHandover:
        """
        Read plans off the freshly fetched notes branch, without the sessions their
        items name.

        :param project_root: The repository whose notes branch holds the plans.
        :param plan_identifiers: The ids of the plans to hand over.
        :raises UnknownPlanError: If the notes branch has no such plan.
        :return: The handover.
        """
        plans = tuple(
            HandoverPlan(
                manifest=PlanManifest.from_yaml(documents.manifest_text),
                roadmap_text=documents.roadmap_text,
            ).without_sessions()
            for documents in (
                PlanDocuments.load(identifier, project_root)
                for identifier in plan_identifiers
            )
        )
        checkout = ProjectCheckout(project_root)
        held_paths = set(
            checkout.notes_branch_paths(ProjectLocation.PULL_REQUEST_PROGRESS)
        )
        branches = [
            item.branch for plan in plans for item in plan.manifest.items if item.branch
        ]
        progress_notes = {}
        for branch in branches:
            path = PurePosixPath(
                ProjectLocation.PULL_REQUEST_PROGRESS
            ) / cls.progress_note_path(branch)
            if path not in held_paths:
                continue
            progress_notes[branch] = (
                checkout.run_git(
                    "show", FetchedBranchReference.PERSONAL_NOTES.file_at(path)
                )
                + "\n"
            )
        return cls(
            plans=plans,
            progress_notes=progress_notes,
            repository_rules=RepositoryRulesStore.from_project_root(
                project_root
            ).read_fetched(),
        )

    @property
    def files(self) -> dict[PurePosixPath, str]:
        """
        Every file of the handover, its guide included, by its path within the
        handover's directory.
        """
        files = {}
        for plan in self.plans:
            plan_directory = PurePosixPath(PlanHandoverLocation.PLANS) / plan.identifier
            files[plan_directory / PlanDocument.MANIFEST] = plan.manifest.text
            files[plan_directory / PlanDocument.ROADMAP] = plan.roadmap_text
        for branch, note in self.progress_notes.items():
            files[
                PurePosixPath(PlanHandoverLocation.PULL_REQUEST_PROGRESS)
                / self.progress_note_path(branch)
            ] = note
        if self.repository_rules.rules:
            files[PurePosixPath(PlanHandoverLocation.REPOSITORY_RULES)] = (
                self.repository_rules.render()
            )
        files[PurePosixPath(PlanHandoverLocation.GUIDE)] = HandoverGuide(
            handover=self
        ).render()
        return files

    @classmethod
    def from_files(cls, files: Mapping[PurePosixPath, str]) -> PlanHandover:
        """
        :param files: The files of a handover, as :attr:`files` names them.
        :return: The handover they hold.
        """
        plans_directory = PurePosixPath(PlanHandoverLocation.PLANS)
        progress_directory = PurePosixPath(PlanHandoverLocation.PULL_REQUEST_PROGRESS)
        plan_identifiers = sorted(
            {
                path.relative_to(plans_directory).parts[0]
                for path in files
                if path.is_relative_to(plans_directory)
            }
        )
        return cls(
            plans=tuple(
                HandoverPlan(
                    manifest=PlanManifest.from_yaml(
                        files[plans_directory / identifier / PlanDocument.MANIFEST]
                    ),
                    roadmap_text=files[
                        plans_directory / identifier / PlanDocument.ROADMAP
                    ],
                )
                for identifier in plan_identifiers
            ),
            progress_notes={
                path.relative_to(progress_directory).with_suffix("").as_posix(): note
                for path, note in files.items()
                if path.is_relative_to(progress_directory)
            },
            repository_rules=RepositoryRules.from_yaml(
                files.get(PurePosixPath(PlanHandoverLocation.REPOSITORY_RULES), "")
            ),
        )

    @classmethod
    def from_directory(cls, directory: Path) -> PlanHandover:
        """
        :param directory: A directory :meth:`write` wrote.
        :return: The handover it holds.
        """
        return cls.from_files(
            {
                PurePosixPath(path.relative_to(directory).as_posix()): path.read_text(
                    encoding="utf-8"
                )
                for path in directory.rglob("*")
                if path.is_file()
            }
        )

    def write(self, directory: Path) -> None:
        """
        Write :attr:`files` into *directory*.

        :param directory: Where to write them, created if missing.
        """
        for path, text in self.files.items():
            target = directory / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def save_to_notes_branch(self, *, project_root: Path) -> None:
        """
        Save every plan onto the notes branch after the plans it depends on, each moved
        onto the checkout's repository, then the progress notes and the repository's
        rules, merged into those already there.

        :param project_root: The repository whose notes branch receives the handover.
        :raises PlanAlreadyTrackedError: If the notes branch already holds one of the
            plans; nothing is saved.
        :raises PlanSaveRefusedError: If a plan's save is refused; the plans before it
            stay saved.
        """
        checkout = ProjectCheckout(project_root)
        checkout.fetch_notes_branch()
        held_plans = set(checkout.notes_branch_paths(ProjectLocation.PLANS))
        for plan in self.plans:
            if (
                PurePosixPath(
                    PlanDocument.MANIFEST.path_within_notes_branch(plan.identifier)
                )
                in held_plans
            ):
                raise PlanAlreadyTrackedError(plan_identifier=plan.identifier)
        read_at = checkout.run_git("rev-parse", FetchedBranchReference.PERSONAL_NOTES)
        checkout_repository = Repository.from_configured_remote(
            GitCommandRunner(project_root)
        )
        for plan in self.plans_in_saving_order:
            PlanSaveScript(plan_identifier=plan.identifier, read_at=read_at).run(
                version=plan.moved_to_repository(checkout_repository).version,
                project_root=project_root,
            )
        store = RepositoryRulesStore.from_project_root(project_root)
        changes = {
            PurePosixPath(ProjectLocation.PULL_REQUEST_PROGRESS)
            / self.progress_note_path(branch): note
            for branch, note in self.progress_notes.items()
        }
        if self.repository_rules.rules:
            changes[store.rules_path] = (
                store.read().with_rules(self.repository_rules).render()
            )
        NotesBranchWriter(store.branch).write(
            NotesFileChanges(changes),
            "Import the progress notes and rules of handed-over plans "
            f"{', '.join(plan.identifier for plan in self.plans)}",
        )

    def remove_from_notes_branch(self, *, project_root: Path) -> None:
        """
        Remove every plan and its items' progress notes from the notes branch.

        :param project_root: The repository whose notes branch holds the plans.
        :raises PlanStillNamedError: If a plan staying on the notes branch depends on an
            item of one of them; nothing is removed.
        """
        checkout = ProjectCheckout(project_root)
        checkout.fetch_notes_branch()
        removed = {plan.identifier for plan in self.plans}
        staying = [
            PlanManifest.from_yaml(
                checkout.run_git(
                    "show", FetchedBranchReference.PERSONAL_NOTES.file_at(path)
                )
            )
            for path in checkout.notes_branch_paths(ProjectLocation.PLANS)
            if path.name == PlanDocument.MANIFEST.value
            and path.parent.name not in removed
        ]
        for plan in self.plans:
            named_by = tuple(
                DependencyReference(item.identifier, manifest.identifier).text
                for manifest in staying
                for item in manifest.items
                if any(
                    DependencyReference.from_text(entry).plan_id == plan.identifier
                    for entry in item.dependencies
                )
            )
            if named_by:
                raise PlanStillNamedError(
                    plan_identifier=plan.identifier, named_by=named_by
                )
        changes: dict[PurePosixPath, str | None] = {
            PurePosixPath(
                PlanDocument.MANIFEST.path_within_notes_branch(plan.identifier)
            ).parent: None
            for plan in self.plans
        }
        changes.update(
            {
                PurePosixPath(ProjectLocation.PULL_REQUEST_PROGRESS)
                / self.progress_note_path(branch): None
                for branch in self.progress_notes
            }
        )
        NotesBranchWriter(
            RepositoryRulesStore.from_project_root(project_root).branch
        ).write(
            NotesFileChanges(changes),
            f"Remove handed-over plans {', '.join(sorted(removed))}",
        )


# %% the guide


@dataclass(frozen=True)
class HandoverGuide(TemplatePage):
    """
    The instructions a coding agent continues a handover's plans from without basstler,
    and every item's state, dependencies and next step.
    """

    handover: PlanHandover
    """
    The handover the guide describes.
    """

    @classproperty
    def template(cls) -> str:
        return PlanHandoverLocation.GUIDE_TEMPLATE.name

    def render(self) -> str:
        """
        :return: The guide, in Markdown.
        """
        return self.render_template(
            handover=self.handover, location=PlanHandoverLocation, status=ItemStatus
        )
