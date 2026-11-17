"""
Compares the receiver classes basstler infers with those a type checker reveals, to find
inferences a checker disputes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from basstler.review_triage.receiver_probes import ReceiverQuestion
from basstler.review_triage.definitions import DefinitionIndex


class ReceiverAgreement(StrEnum):
    """
    How the class basstler inferred for one receiver relates to the one a checker
    revealed.
    """

    SAME_CLASS = "same class"
    """
    Both name the same class.
    """

    SUBCLASS_REVEALED = "subclass revealed"
    """
    The checker revealed a subclass of the inferred class, which the inference allows.
    """

    BASE_CLASS_REVEALED = "base class revealed"
    """
    The checker revealed a class the inferred one inherits from.
    """

    UNRELATED_CLASSES = "unrelated classes"
    """
    Neither class inherits from the other.
    """

    INFERRED_ONLY = "inferred only"
    """
    Only basstler answered the receiver.
    """

    REVEALED_ONLY = "revealed only"
    """
    Only the checker answered the receiver.
    """

    @property
    def disputes_inference(self) -> bool:
        """
        Whether the checker answered the receiver with a class the inferred one may not
        be an instance of.
        """
        return self in (
            ReceiverAgreement.BASE_CLASS_REVEALED,
            ReceiverAgreement.UNRELATED_CLASSES,
        )


@dataclass(frozen=True)
class ReceiverCrossCheck:
    """
    The receivers of one pull request answered by basstler, by a checker or by both.
    """

    inferred: dict[ReceiverQuestion, str]
    """
    The class basstler inferred for each receiver it answered.
    """

    revealed: dict[ReceiverQuestion, str]
    """
    The class the checker revealed for each receiver it answered.
    """

    definitions: DefinitionIndex
    """
    The base commit's definitions, which say which class inherits from which.
    """

    def inherits(self, subclass: str, base: str) -> bool:
        """
        :param subclass: The name of a class.
        :param base: The name of another class.
        :return: Whether a class of the first name inherits from one of the second.
        """
        return any(
            definition.name == subclass
            for definition in self.definitions.subclasses_of(base)
        )

    def compare(self, question: ReceiverQuestion) -> ReceiverAgreement:
        """
        :param question: A receiver at least one of the two answered.
        :return: How the two answers relate.
        """
        inferred = self.inferred.get(question)
        revealed = self.revealed.get(question)
        if revealed is None:
            return ReceiverAgreement.INFERRED_ONLY
        if inferred is None:
            return ReceiverAgreement.REVEALED_ONLY
        if inferred == revealed:
            return ReceiverAgreement.SAME_CLASS
        if self.inherits(revealed, inferred):
            return ReceiverAgreement.SUBCLASS_REVEALED
        if self.inherits(inferred, revealed):
            return ReceiverAgreement.BASE_CLASS_REVEALED
        return ReceiverAgreement.UNRELATED_CLASSES

    def compare_all(self) -> dict[ReceiverQuestion, ReceiverAgreement]:
        """
        :return: How the answers relate for every receiver either answered.
        """
        return {
            question: self.compare(question)
            for question in self.inferred.keys() | self.revealed.keys()
        }
