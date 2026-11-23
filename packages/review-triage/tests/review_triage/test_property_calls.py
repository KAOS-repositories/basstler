"""
Judging a property read turned into a call of a method, against the definitions of both
commits.
"""

from __future__ import annotations

from basstler.review_triage.comparison import (
    FileTriager,
    FileVerdict,
    JudgmentContext,
    MechanicalChange,
    MechanicalFile,
    ProseComparison,
)
from basstler.review_triage.keyword_arguments import KeywordArgumentComparison
from basstler.review_triage.property_calls import (
    PropertyCallChange,
    UnprovenPropertyCall,
    UnprovenReplacement,
)
from basstler.review_triage.renames import RenameMap

from .samples import FileSample

# %% verdicts


def triaged(sample: FileSample, renames: RenameMap) -> FileVerdict:
    """
    :param sample: A file in two versions.
    :param renames: The renames of the pull request.
    :return: The sample's verdict, each version's definitions as its commit's.
    """
    context = JudgmentContext(
        renames,
        sample.base_definitions(),
        head_definitions=sample.head_definitions(),
    )
    triager = FileTriager(context, (KeywordArgumentComparison(), ProseComparison()))
    return triager.triage(sample.change())


def test_a_property_read_called_as_a_method_reproducing_it_is_mechanical(
    poses_renamed: RenameMap,
):
    """
    Reading a property becomes calling a method without arguments whose body is the
    property's, under the pull request's renames.
    """
    sample = FileSample.PROPERTY_READ_AS_METHOD_CALL
    assert triaged(sample, poses_renamed) == MechanicalFile(
        sample.change(),
        frozenset(
            {
                PropertyCallChange.PROPERTIES_CALLED,
                MechanicalChange.RENAME,
                MechanicalChange.IMPORTS,
            }
        ),
    )


def test_a_method_call_not_reproducing_the_property_is_the_reason_for_review(
    poses_renamed: RenameMap,
):
    """
    A method whose body differs from the property's, a receiver of unknown class
    reaching such a method, and a method that was no property all need review.
    """
    sample = FileSample.PROPERTY_READ_AS_METHOD_CALL_UNPROVEN
    expected = [
        (
            "return pose.to_transform()",
            "to_transform",
            UnprovenReplacement.NOT_REPRODUCED,
            ("PlanarPose.as_matrix",),
        ),
        (
            "return [pose.to_transform()]",
            "to_transform",
            UnprovenReplacement.RECEIVER_CLASS_UNKNOWN,
            ("PlanarPose.as_matrix",),
        ),
        (
            "return pose.offset()",
            "offset",
            UnprovenReplacement.NOT_A_PROPERTY,
            ("Pose.offset",),
        ),
    ]
    assert triaged(sample, poses_renamed).reasons == tuple(
        UnprovenPropertyCall(sample.head_line(code), method, cause, definitions)
        for code, method, cause, definitions in expected
    )


def test_an_abstract_method_of_an_abstract_base_class_is_never_reached(
    poses_renamed: RenameMap,
):
    """
    An instance never runs a method its abstract base class leaves abstract, so only the
    override has to reproduce the property.
    """
    sample = FileSample.PROPERTY_READ_AS_ABSTRACT_INTERFACE_METHOD
    assert triaged(sample, poses_renamed) == MechanicalFile(
        sample.change(),
        frozenset(
            {
                PropertyCallChange.PROPERTIES_CALLED,
                MechanicalChange.RENAME,
                MechanicalChange.IMPORTS,
            }
        ),
    )


def test_a_class_sharing_the_abstract_base_class_name_leaves_its_method_unreached(
    poses_renamed: RenameMap,
):
    """
    Another class of the abstract base class's name that does not define the method does
    not make the abstract method reachable.
    """
    sample = FileSample.PROPERTY_READ_AS_ABSTRACT_METHOD_OF_A_SHARED_CLASS_NAME
    assert triaged(sample, poses_renamed) == MechanicalFile(
        sample.change(),
        frozenset(
            {
                PropertyCallChange.PROPERTIES_CALLED,
                MechanicalChange.RENAME,
                MechanicalChange.IMPORTS,
            }
        ),
    )


def test_an_abstract_method_of_a_plain_class_is_the_reason_for_review(
    poses_renamed: RenameMap,
):
    """
    A class that does not derive from :class:`abc.ABC` lets an instance run a method it
    marks abstract, so the call may reach a decorated method.
    """
    sample = FileSample.PROPERTY_READ_AS_UNENFORCED_ABSTRACT_METHOD
    assert triaged(sample, poses_renamed).reasons == tuple(
        UnprovenPropertyCall(
            sample.head_line(code),
            "to_transform",
            UnprovenReplacement.DECORATED_METHOD,
            ("Placeable.to_transform",),
        )
        for code in (
            "return pose.to_transform()",
            "return pose.to_transform().entries",
        )
    )


def test_a_call_reaching_only_abstract_methods_is_the_reason_for_review(
    poses_renamed: RenameMap,
):
    """
    A call whose every method is abstract on a class with :class:`abc.ABCMeta` as its
    metaclass runs nothing the head commit defines.
    """
    sample = FileSample.PROPERTY_READ_AS_UNIMPLEMENTED_ABSTRACT_METHOD
    assert triaged(sample, poses_renamed).reasons == tuple(
        UnprovenPropertyCall(
            sample.head_line(code), "to_transform", UnprovenReplacement.NO_METHOD, ()
        )
        for code in (
            "return pose.to_transform()",
            "return pose.to_transform().entries",
        )
    )
