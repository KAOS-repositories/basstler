"""
Classify one item's dependencies as ready or not-ready to build on, reusing the plan
site's own live-state classification and readiness rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from basstler.github.pull_request_state import LivePullRequests
from basstler.plan.dependencies import Dependency, DependencyResolver, PlanDirectory
from basstler.plan.structure import Plan


class UnknownItemError(ValueError):
    """
    Raised when the requested item id doesn't exist in the plan.
    """


class ReadinessField(StrEnum):
    """
    The keys one dependency's readiness carries once serialized.
    """

    IDENTIFIER = "identifier"
    TITLE = "title"
    LIVE_STATE = "live_state"
    IS_READY = "is_ready"


@dataclass(frozen=True)
class DependencyReadiness:
    """
    One ``depends_on`` entry, and whether it is safe to build on.
    """

    dependency: Dependency
    """
    The dependency, with its live state already classified.
    """

    must_be_merged: bool = False
    """
    Whether the dependent needs the dependency merged, not only out of draft.
    """

    @property
    def is_ready(self) -> bool:
        """
        Whether the dependent can start as far as this dependency goes.
        """
        return self.dependency.releases_dependent(self.must_be_merged)

    def to_json(self) -> dict[str, Any]:
        """
        This readiness as the one entry the item brief serializes for it.
        """
        live_state = self.dependency.live_state
        return {
            ReadinessField.IDENTIFIER.value: self.dependency.reference.text,
            ReadinessField.TITLE.value: self.dependency.title,
            ReadinessField.LIVE_STATE.value: live_state.value if live_state else None,
            ReadinessField.IS_READY.value: self.is_ready,
        }

    @classmethod
    def of_item(
        cls,
        plan: Plan,
        item_identifier: str,
        live_pull_requests: LivePullRequests,
        plan_directory: PlanDirectory | None = None,
    ) -> list[DependencyReadiness]:
        """
        Classify every dependency of ``item_identifier`` as ready or not.

        :param plan: The already-validated plan.
        :param item_identifier: The effective identifier (``id`` or ``branch``) of the
            item whose dependencies should be checked.
        :param live_pull_requests: What was read of every repository referenced by the
            plan's items, and by any plan they depend on.
        :param plan_directory: The other plans a ``<plan-id>/<item-id>`` dependency
            resolves against, or ``None`` when only this plan's own items are available.
        :raises UnknownItemError: If ``item_identifier`` isn't in the plan.
        :return: One readiness per entry in the item's ``depends_on``, in that order.
        """
        item = plan.items_by_identifier.get(item_identifier)
        if item is None:
            raise UnknownItemError(f"no item {item_identifier!r} in plan {plan.id!r}")

        resolver = DependencyResolver(plan=plan, plan_directory=plan_directory)
        resolver.classify_live_states(live_pull_requests)
        return [
            cls(resolver.resolve(entry), entry in item.depends_on_merged)
            for entry in item.depends_on
        ]
