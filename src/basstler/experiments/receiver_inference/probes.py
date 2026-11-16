"""
Inferences that answer no receiver, or record what a triage asks about.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from basstler.review_triage.calls import CallScope, ReceiverInference
from basstler.review_triage.receiver_probes import ExpressionSpan, ReceiverQuestion
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.signatures import SignatureReader

# %% the triage's questions


@dataclass(frozen=True)
class NoInference(ReceiverInference):
    """
    Answers no receiver.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        return None


@dataclass(frozen=True)
class AnswerRecording(ReceiverInference):
    """
    Answers as another inference does, recording each receiver whose file is known that
    it is asked about, and the class it answers each with that the base commit defines.
    """

    inference: ReceiverInference
    """
    The inference answering.
    """

    asked: set[ReceiverQuestion] = field(default_factory=set)
    """
    Every receiver asked about so far.
    """

    answers: dict[ReceiverQuestion, str] = field(default_factory=dict)
    """
    The class every receiver answered so far was answered with.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        found = self.inference.receiver_class(receiver, scope, reader, renames)
        if scope.module is None:
            return found
        question = ReceiverQuestion(
            scope.module.text, ExpressionSpan.of(receiver, scope.module.text)
        )
        self.asked.add(question)
        if found is not None and reader.definitions.classes_named(found):
            self.answers[question] = found
        return found
