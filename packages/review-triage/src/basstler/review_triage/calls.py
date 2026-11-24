"""
The definitions a call may reach: a resolution reads from the call's syntax what it
reaches its callee through, as a target that knows which definitions that may be.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import Enum, auto

from basstler.review_triage.definitions import (
    ClassDefinition,
    Definition,
    DefinitionIndex,
    FunctionDefinition,
    ReceiverName,
)
from basstler.review_triage.name_scopes import (
    AssignedValue,
    DeclaredType,
    DefinitionReference,
    ImportedDefinition,
    IteratedElement,
    LocalDefinition,
    NameBinding,
    NameScope,
)
from basstler.review_triage.python_source import (
    AnnotatedType,
    ContainerKind,
    PythonSource,
)
from basstler.review_triage.receiver_probes import RevealedReceivers
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR, RenameMap
from basstler.review_triage.signatures import (
    STATIC_METHOD,
    Signature,
    SignatureReader,
)

SELF_TYPE = "Self"
"""
The typing name of the class of the instance or class a method is called on.
"""

CLASS_OBJECT = "type"
"""
The class of every class, ``type[X]`` declaring the class ``X`` itself.
"""

NEXT_BUILTIN = "next"
"""
The builtin returning the next element of an iterator.
"""

COLLECTING_BUILTINS: dict[str, str] = {
    "list": "list",
    "sorted": "list",
    "tuple": "tuple",
    "set": "set",
    "frozenset": "frozenset",
    "iter": "Iterator",
    "reversed": "Iterator",
}
"""
The builtins returning the elements of their first argument in a container, with the
class of that container.
"""

COMPREHENSION_CLASSES: dict[type[ast.expr], str] = {
    ast.ListComp: "list",
    ast.SetComp: "set",
    ast.GeneratorExp: "Generator",
}
"""
The comprehensions giving one element each, with the class of what they make.
"""

# %% where a call is made


@dataclass(frozen=True)
class CallScope:
    """
    What the code around a call tells about the names it uses.
    """

    enclosing_class: str | None = None
    """
    The name of the innermost class whose body holds the call.
    """

    parameter_types: dict[str, str] = field(default_factory=dict)
    """
    The class each parameter of the innermost enclosing function is annotated with,
    for the parameters the function never assigns to.
    """

    name_scopes: tuple[NameScope, ...] = ()
    """
    The scopes enclosing the call, the module's first and the innermost last.
    """

    imports: NameScope = field(default_factory=NameScope)
    """
    The names the imports of the file holding the call bind, wherever they are.
    """

    file_definitions: DefinitionIndex = field(default_factory=DefinitionIndex)
    """
    The definitions of the base version of the file holding the call.
    """

    module: PythonSource | None = None
    """
    The base version of the file holding the call, ``None`` when unknown.
    """

    revealed_receivers: RevealedReceivers | None = None
    """
    The classes a type checker reveals for the pull request's receivers, ``None``
    without a type checker.
    """

    def defined_class_name(self, name: str) -> str:
        """
        :param name: A class name as the file spells it.
        :return: The name the class is defined under, which differs from *name* when
            the file imports it under another name.
        """
        bindings = self.imports.bindings.get(name, ())
        if len(bindings) == 1 and isinstance(bindings[0], ImportedDefinition):
            return bindings[0].defined_name
        return name


# %% targets


@dataclass(frozen=True)
class ReachableDefinition:
    """
    One definition a call may reach, with the signature of calling it.
    """

    qualified_name: str
    """
    Its name, after the name of the class defining it for a method.
    """

    signature: Signature | None
    """
    The signature of calling it, ``None`` when it cannot be read.
    """

    definition: Definition | None = None
    """
    The function, method or class reached, ``None`` when it is not read.
    """


class CallTarget(ABC):
    """
    What one call reaches its callee through, and so the definitions it may reach.
    """

    @abstractmethod
    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        """
        :param reader: Reads the base commit's signatures.
        :return: Each definition the call may reach.
        """

    @abstractmethod
    def in_base(self, renames: RenameMap) -> CallTarget:
        """
        :param renames: The renames the pull request makes throughout.
        :return: This target with every name the base commit spells differently.
        """

    def looked_up_names(self) -> frozenset[str]:
        """
        :return: The names whose definitions this target looks up by name, to find
            them together with other calls' in one search.
        """
        return frozenset()

    def known_by_name_only(self, reader: SignatureReader) -> bool:
        """
        :param reader: Reads the base commit's signatures.
        :return: Whether every definition of the callee's name may be reached, for want
            of knowing which class it belongs to.
        """
        return False


@dataclass(frozen=True)
class NamedTarget(CallTarget):
    """
    A callee known by its name alone: every definition of the name may be reached.
    """

    callee: str
    """
    The last name of the called expression.
    """

    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        if self.callee.startswith("__"):
            return []
        return [
            ReachableDefinition(
                definition.qualified_name, reader.signature_of(definition), definition
            )
            for definition in reader.definitions.definitions_of(self.callee)
        ]

    def in_base(self, renames: RenameMap) -> CallTarget:
        return replace(self, callee=renames.original_identifier(self.callee))

    def looked_up_names(self) -> frozenset[str]:
        """
        :meth:`CallTarget.looked_up_names`: the callee's name.
        """
        return frozenset({self.callee})

    def known_by_name_only(self, reader: SignatureReader) -> bool:
        """
        :meth:`CallTarget.known_by_name_only`: always.
        """
        return True


class ClassReach(Enum):
    """
    Which classes related to the receiver's class may define the method a call reaches.
    """

    HIERARCHY = auto()
    """
    The class, the classes it inherits from and those inheriting from it: the
    receiver is an instance of the class or of a subclass.
    """

    ANCESTORS = auto()
    """
    Only the classes it, or a subclass, inherits from: the receiver is ``super()``.
    """


@dataclass(frozen=True)
class MethodTarget(CallTarget):
    """
    A method of an object of a known class, or of a subclass of it.
    """

    callee: str
    """
    The method's name.
    """

    class_name: str
    """
    The name of the receiver's class.
    """

    reach: ClassReach = ClassReach.HIERARCHY
    """
    Which related classes may define the method reached.
    """

    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        index = reader.definitions
        if not index.reads_hierarchy_of(self.class_name):
            return [
                ReachableDefinition(self.qualified_method_name(self.class_name), None)
            ]
        lower = [
            *index.classes_named(self.class_name),
            *index.subclasses_of(self.class_name),
        ]
        upper = index.ancestors_of(lower)
        classes = [*lower, *upper]
        if self.reach is ClassReach.ANCESTORS:
            classes = [definition for definition in upper if definition not in lower]
        return [
            ReachableDefinition(
                self.qualified_method_name(definition.name),
                reader.method_signature(definition, self.callee),
                definition.method(self.callee),
            )
            for definition in classes
            if reader.defines(definition, self.callee)
        ]

    def qualified_method_name(self, class_name: str) -> str:
        """
        :param class_name: The name of a class the method may be defined in.
        :return: The method's name after the class's.
        """
        return f"{class_name}{DOTTED_NAME_SEPARATOR}{self.callee}"

    def in_base(self, renames: RenameMap) -> CallTarget:
        return replace(
            self,
            callee=renames.original_identifier(self.callee),
            class_name=renames.original_identifier(self.class_name),
        )


@dataclass(frozen=True)
class ClassTarget(CallTarget):
    """
    A class of a known name, or a subclass of it, called to make an instance.
    """

    class_name: str
    """
    The class's name.
    """

    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        index = reader.definitions
        if not index.reads_hierarchy_of(self.class_name):
            return [ReachableDefinition(self.class_name, None)]
        classes: list[ClassDefinition] = [
            *index.classes_named(self.class_name),
            *index.subclasses_of(self.class_name),
        ]
        return [
            ReachableDefinition(
                definition.qualified_name, reader.signature_of(definition), definition
            )
            for definition in classes
        ]

    def in_base(self, renames: RenameMap) -> CallTarget:
        return replace(self, class_name=renames.original_identifier(self.class_name))


@dataclass(frozen=True)
class AttributeMethodTarget(CallTarget):
    """
    A method of an attribute of ``self``: of the class the enclosing class declares it
    to hold, or found by name when no class is declared.
    """

    callee: str
    """
    The method's name.
    """

    owner_class: str
    """
    The name of the class whose instance holds the attribute.
    """

    attribute: str
    """
    The attribute's name.
    """

    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        declared = reader.attribute_class(self.owner_class, self.attribute)
        if declared is None:
            return NamedTarget(self.callee).reachable_definitions(reader)
        return MethodTarget(self.callee, declared).reachable_definitions(reader)

    def in_base(self, renames: RenameMap) -> CallTarget:
        return replace(
            self,
            callee=renames.original_identifier(self.callee),
            owner_class=renames.original_identifier(self.owner_class),
            attribute=renames.original_identifier(self.attribute),
        )

    def known_by_name_only(self, reader: SignatureReader) -> bool:
        """
        :meth:`CallTarget.known_by_name_only`: when no class is declared for the
        attribute.
        """
        return reader.attribute_class(self.owner_class, self.attribute) is None


@dataclass(frozen=True)
class InferredMethodTarget(CallTarget):
    """
    A method of a receiver whose class an inference finds, found by name when it finds
    none or the base commit defines no class of that name.
    """

    callee: str
    """
    The method's name.
    """

    receiver: ast.expr
    """
    The expression the method is called on, in the base version.
    """

    scope: CallScope
    """
    What the code around the call tells about the names it uses.
    """

    inference: ReceiverInference
    """
    Finds the receiver's class.
    """

    renames: RenameMap = RenameMap()
    """
    The renames from the names the receiver is spelled with to the base commit's.
    """

    def receiver_class(self, reader: SignatureReader) -> str | None:
        """
        :param reader: Reads the base commit's signatures.
        :return: The base commit's name of the receiver's class, ``None`` when it is
            not found or the base commit defines no class of that name.
        """
        found = self.inference.receiver_class(
            self.receiver, self.scope, reader, self.renames
        )
        if found is None or not reader.definitions.classes_named(found):
            return None
        return found

    def reachable_definitions(
        self, reader: SignatureReader
    ) -> list[ReachableDefinition]:
        owner = self.receiver_class(reader)
        if owner is None:
            return NamedTarget(self.callee).reachable_definitions(reader)
        return MethodTarget(self.callee, owner).reachable_definitions(reader)

    def in_base(self, renames: RenameMap) -> CallTarget:
        return replace(
            self, callee=renames.original_identifier(self.callee), renames=renames
        )

    def looked_up_names(self) -> frozenset[str]:
        """
        :meth:`CallTarget.looked_up_names`: the method's name, for finding it by name.
        """
        return frozenset({self.callee})

    def known_by_name_only(self, reader: SignatureReader) -> bool:
        """
        :meth:`CallTarget.known_by_name_only`: when the receiver's class is not found.
        """
        return self.receiver_class(reader) is None


# %% receiver classes


class ReceiverInference(ABC):
    """
    Finds the class of the object a method is called on.
    """

    @abstractmethod
    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        """
        :param receiver: The expression a method is called on, in the base version.
        :param scope: What the code around the call tells about the names it uses.
        :param reader: Reads the base commit's definitions.
        :param renames: The renames from the names the receiver is spelled with to the
            base commit's.
        :return: The base commit's name of the class the receiver is an instance of,
            or of a subclass of, ``None`` when not found.
        """


@dataclass(frozen=True)
class AnnotationInference(ReceiverInference):
    """
    Follows the receiver through the bindings of the names it uses, the classes and
    functions it calls, the containers it iterates over and the annotations of the
    parameters, attributes and returns it reaches.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        found = ReceiverWalk(scope, reader, renames).type_of(receiver, frozenset())
        if found is None or found.class_name == CLASS_OBJECT:
            return None
        return found.class_name


@dataclass(frozen=True)
class RevealedInference(ReceiverInference):
    """
    Answers each receiver with the class a type checker reveals for it in the base
    commit.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        if scope.module is None or scope.revealed_receivers is None:
            return None
        return scope.revealed_receivers.class_of(receiver, scope.module.text)


@dataclass(frozen=True)
class CombinedInference(ReceiverInference):
    """
    Answers each receiver as the first of several inferences that answers it.
    """

    inferences: tuple[ReceiverInference, ...] = (
        AnnotationInference(),
        RevealedInference(),
    )
    """
    The inferences asked, in order: basstler's own, then the type checker for each
    receiver it leaves open.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        answers = (
            inference.receiver_class(receiver, scope, reader, renames)
            for inference in self.inferences
        )
        return next((answer for answer in answers if answer is not None), None)


@dataclass(frozen=True)
class ReceiverWalk:
    """
    One search of :class:`AnnotationInference` for what the expressions of one scope
    are, every name being followed through each of its bindings that may reach it.
    """

    scope: CallScope
    """
    What the code around the expressions tells about the names they use.
    """

    reader: SignatureReader
    """
    Reads the base commit's definitions.
    """

    renames: RenameMap
    """
    The renames from the names the expressions are spelled with to the base commit's.
    """

    def type_of(
        self, expression: ast.expr, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param expression: An expression in the scope.
        :param followed: The bindings whose values the search is inside of.
        :return: What its value is, the classes named as the base commit names them,
            ``None`` when not found.
        """
        if isinstance(expression, ast.Name):
            return self.name_type(expression, followed)
        if isinstance(expression, ast.Call):
            return self.returned_type(expression, followed)
        if isinstance(expression, ast.Attribute):
            owner = self.type_of(expression.value, followed)
            if owner is None or owner.arguments:
                return None
            return self.reader.attribute_type(
                owner.class_name, self.renames.original_identifier(expression.attr)
            )
        if isinstance(expression, ast.Subscript):
            return self.indexed_type(expression, followed)
        if type(expression) in COMPREHENSION_CLASSES:
            walk = self.within(NameScope.opened_by(expression))
            return AnnotatedType(
                COMPREHENSION_CLASSES[type(expression)],
                (walk.type_of(expression.elt, followed),),
            )
        if isinstance(expression, ast.IfExp):
            return self.agreed_type(
                self.type_of(branch, followed)
                for branch in (expression.body, expression.orelse)
            )
        return None

    def within(self, scope: NameScope) -> ReceiverWalk:
        """
        :param scope: A scope nested in the innermost one, such as a comprehension's.
        :return: This search for the expressions of that scope.
        """
        nested = replace(self.scope, name_scopes=(*self.scope.name_scopes, scope))
        return replace(self, scope=nested)

    @staticmethod
    def agreed_type(
        found: Iterable[AnnotatedType | None],
    ) -> AnnotatedType | None:
        """
        :param found: What each of the values an expression may have is.
        :return: What all of them are, ``None`` when they disagree or one is not found.
        """
        distinct = set(found)
        if len(distinct) != 1:
            return None
        return distinct.pop()

    # %%% names

    def visible_bindings(self, name: str) -> tuple[NameBinding, ...] | None:
        """
        :param name: A name the innermost scope uses.
        :return: Every binding of it in the scope it is found in, with every import of
            it in the file, whose scope is not known; empty for a name nothing binds,
            a builtin, and ``None`` when the scopes are unknown.
        """
        scopes = self.scope.name_scopes
        if not scopes:
            return None
        imports = self.scope.imports
        imported = imports.bindings.get(name, ())
        for depth, scope in enumerate(reversed(scopes)):
            if scope.class_body and depth > 0:
                continue
            if name in scope.bindings:
                return scope.bindings[name] + imported
        if not imported and imports.imports_everything:
            return (ImportedDefinition(name),)
        return imported

    def reaching_bindings(self, use: ast.Name) -> tuple[NameBinding, ...] | None:
        """
        :param use: A name the innermost scope reads.
        :return: :meth:`visible_bindings` of the name, narrowed to the bindings the
            order of the innermost scope's statements shows reach the use.
        """
        scopes = self.scope.name_scopes
        if scopes and use.id in scopes[-1].bindings:
            order = scopes[-1].statement_order
            reaching = None if order is None else order.reaching_bindings(use)
            if reaching is not None:
                return reaching
        return self.visible_bindings(use.id)

    def name_type(
        self, use: ast.Name, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param use: A name the innermost scope reads.
        :param followed: The bindings whose values the search is inside of.
        :return: What the value it refers to is.
        """
        if use.id == ReceiverName.INSTANCE and self.scope.enclosing_class is not None:
            return AnnotatedType(
                self.renames.original_identifier(self.scope.enclosing_class)
            )
        bindings = self.reaching_bindings(use)
        if not bindings or followed & set(bindings):
            return None
        return self.agreed_type(
            self.binding_type(binding, followed | {binding}) for binding in bindings
        )

    def binding_type(
        self, binding: NameBinding, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param binding: A binding of a name.
        :param followed: The bindings whose values the search is inside of, this one
            included.
        :return: What the value it gives the name is.
        """
        if isinstance(binding, AssignedValue):
            return self.type_of(binding.value, followed)
        if isinstance(binding, IteratedElement):
            iterated = self.type_of(binding.iterable, followed)
            return self.element_type(iterated)
        if isinstance(binding, DeclaredType):
            declared = AnnotatedType.from_annotation(binding.annotation)
            return None if declared is None else declared.in_base(self.renames)
        if isinstance(binding, DefinitionReference):
            definitions = self.referenced_definitions(binding)
            if not definitions or not all(
                isinstance(definition, ClassDefinition) for definition in definitions
            ):
                return None
            name = definitions[0].name
            return AnnotatedType(CLASS_OBJECT, (AnnotatedType(name),))
        return None

    def referenced_definitions(
        self, binding: DefinitionReference
    ) -> tuple[Definition, ...]:
        """
        :param binding: A binding of a name to a definition.
        :return: Every definition the name may refer to: those of the file for a
            ``class`` or ``def`` statement, those of the commit otherwise.
        """
        name = self.renames.original_identifier(binding.defined_name)
        index = self.reader.definitions
        if isinstance(binding, LocalDefinition):
            index = self.scope.file_definitions
        return index.definitions_of(name)

    # %%% containers

    def standard_container(self, value: AnnotatedType | None) -> AnnotatedType | None:
        """
        :param value: What a value is.
        :return: It when it is a standard container declaring what it holds, and the
            base commit defines no class of its name, ``None`` otherwise.
        """
        if value is None or value.container_kind is None:
            return None
        if self.reader.definitions.classes_named(value.class_name):
            return None
        return value

    def element_type(self, iterated: AnnotatedType | None) -> AnnotatedType | None:
        """
        :param iterated: What a value iterated over is.
        :return: What each element it gives is.
        """
        container = self.standard_container(iterated)
        return None if container is None else container.element

    def indexed_type(
        self, subscript: ast.Subscript, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param subscript: An indexing or slicing in the scope.
        :param followed: The bindings whose values the search is inside of.
        :return: What it gives.
        """
        container = self.standard_container(self.type_of(subscript.value, followed))
        if container is None:
            return None
        if not isinstance(subscript.slice, ast.Slice):
            return container.item
        if container.container_kind is ContainerKind.SEQUENCE:
            return container
        return None

    # %%% calls

    def returned_type(
        self, call: ast.Call, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param call: A call in the scope.
        :param followed: The bindings whose values the search is inside of.
        :return: What the value it returns is.
        """
        function = call.func
        if isinstance(function, ast.Attribute):
            owner = self.type_of(function.value, followed)
            if owner is None:
                return None
            method = self.renames.original_identifier(function.attr)
            return self.method_result(owner, method, call)
        if isinstance(function, ast.Name):
            bindings = self.visible_bindings(function.id)
            if bindings == ():
                return self.builtin_result(function.id, call, followed)
            functions = self.referenced_functions(bindings)
            if functions:
                return self.agreed_type(
                    self.function_return(called, call, None) for called in functions
                )
        callee = self.type_of(function, followed)
        if callee is None or callee.class_name != CLASS_OBJECT:
            return None
        return callee.arguments[0]

    def referenced_functions(
        self, bindings: tuple[NameBinding, ...] | None
    ) -> list[FunctionDefinition]:
        """
        :param bindings: The bindings of a called name.
        :return: The functions the name refers to, empty when it may refer to
            anything else.
        """
        if bindings is None or len(bindings) != 1:
            return []
        binding = bindings[0]
        if not isinstance(binding, DefinitionReference):
            return []
        candidates = [
            definition
            for definition in self.referenced_definitions(binding)
            if isinstance(definition, ClassDefinition) or definition.owner is None
        ]
        functions = [
            definition
            for definition in candidates
            if isinstance(definition, FunctionDefinition)
        ]
        return functions if len(functions) == len(candidates) else []

    def builtin_result(
        self, name: str, call: ast.Call, followed: frozenset[NameBinding]
    ) -> AnnotatedType | None:
        """
        :param name: The builtin function called.
        :param call: The call.
        :param followed: The bindings whose values the search is inside of.
        :return: What it returns: the next element for ``next``, a container of the
            elements for the builtins collecting them.
        """
        if not call.args:
            return None
        element = self.element_type(self.type_of(call.args[0], followed))
        if name == NEXT_BUILTIN:
            return element
        if name not in COLLECTING_BUILTINS:
            return None
        return AnnotatedType(COLLECTING_BUILTINS[name], (element,))

    def method_result(
        self, owner: AnnotatedType, method: str, call: ast.Call
    ) -> AnnotatedType | None:
        """
        :param owner: What the receiver of a method call is.
        :param method: The base commit's name of the method.
        :param call: The call.
        :return: What the method returns.
        """
        container = self.standard_container(owner)
        if container is not None:
            return container.method_result(method)
        receiver = owner
        if owner.class_name == CLASS_OBJECT:
            receiver = owner.arguments[0] if len(owner.arguments) == 1 else None
        index = self.reader.definitions
        if receiver is None or not index.reads_hierarchy_of(receiver.class_name):
            return None
        classes = list(index.classes_named(receiver.class_name))
        methods = [
            found
            for definition in [*classes, *index.ancestors_of(classes)]
            if (found := definition.method(method)) is not None
        ]
        if not methods:
            return None
        return self.agreed_type(
            self.function_return(found, call, AnnotatedType(receiver.class_name))
            for found in methods
        )

    def function_return(
        self,
        function: FunctionDefinition,
        call: ast.Call,
        receiver: AnnotatedType | None,
    ) -> AnnotatedType | None:
        """
        :param function: A function the call may reach.
        :param call: The call.
        :param receiver: What the method's receiver is, ``None`` for a function.
        :return: What it returns for the call's arguments.
        """
        parameter = function.class_argument_parameter
        if parameter is None:
            if function.return_type == AnnotatedType(SELF_TYPE):
                return receiver
            return function.return_type
        argument = next(
            (
                keyword.value
                for keyword in call.keywords
                if keyword.arg is not None
                and self.renames.original_identifier(keyword.arg) == parameter
            ),
            None,
        )
        bound = function.owner is not None and STATIC_METHOD not in function.decorators
        if argument is None and parameter in function.parameters:
            position = function.parameters.index(parameter) - int(bound)
            if 0 <= position < len(call.args):
                argument = call.args[position]
        if not isinstance(argument, (ast.Name, ast.Attribute)):
            return None
        name = self.renames.original_identifier(PythonSource.referenced_name(argument))
        if not self.reader.definitions.classes_named(name):
            return None
        return AnnotatedType(name)


# %% resolutions


class CalleeResolution(ABC):
    """
    Recognises one way a call reaches its callee.
    """

    @abstractmethod
    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        """
        :param function: The called expression of a call.
        :param scope: What the code around the call tells.
        :return: What the call reaches its callee through, ``None`` when it does not
            reach it this way.
        """


@dataclass(frozen=True)
class OwnClass(CalleeResolution):
    """
    ``cls(...)``: the enclosing class or one inheriting from it.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not (isinstance(function, ast.Name) and function.id == ReceiverName.CLASS):
            return None
        if scope.enclosing_class is None:
            return None
        return ClassTarget(scope.enclosing_class)


@dataclass(frozen=True)
class InstanceMethod(CalleeResolution):
    """
    ``self.method(...)`` or ``cls.method(...)``: a method of the enclosing class's
    hierarchy.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id in (ReceiverName.INSTANCE, ReceiverName.CLASS)
            and scope.enclosing_class is not None
        ):
            return None
        return MethodTarget(function.attr, scope.enclosing_class)


@dataclass(frozen=True)
class ParentMethod(CalleeResolution):
    """
    ``super().method(...)``: a method of a class the enclosing class inherits from.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Call)
            and isinstance(function.value.func, ast.Name)
            and function.value.func.id == ReceiverName.PARENT
            and not function.value.args
            and scope.enclosing_class is not None
        ):
            return None
        return MethodTarget(function.attr, scope.enclosing_class, ClassReach.ANCESTORS)


@dataclass(frozen=True)
class AttributeMethod(CalleeResolution):
    """
    ``self.attribute.method(...)``: a method of the class the enclosing class declares
    the attribute to hold.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Attribute)
            and isinstance(function.value.value, ast.Name)
            and function.value.value.id == ReceiverName.INSTANCE
            and scope.enclosing_class is not None
        ):
            return None
        return AttributeMethodTarget(
            function.attr, scope.enclosing_class, function.value.attr
        )


@dataclass(frozen=True)
class ParameterMethod(CalleeResolution):
    """
    ``parameter.method(...)``: a method of the class the enclosing function annotates
    the parameter with.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id in scope.parameter_types
        ):
            return None
        annotated = scope.parameter_types[function.value.id]
        return MethodTarget(function.attr, scope.defined_class_name(annotated))


@dataclass(frozen=True)
class InferredReceiverMethod(CalleeResolution):
    """
    ``receiver.method(...)``: a method of the class an inference finds the receiver to
    be an instance of.
    """

    inference: ReceiverInference = field(default_factory=CombinedInference)
    """
    Finds the receiver's class.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if not isinstance(function, ast.Attribute):
            return None
        return InferredMethodTarget(
            function.attr, function.value, scope, self.inference
        )


@dataclass(frozen=True)
class NamedCallee(CalleeResolution):
    """
    Any other call: every definition of the called name may be reached.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        if isinstance(function, ast.Name):
            return NamedTarget(function.id)
        if isinstance(function, ast.Attribute):
            return NamedTarget(function.attr)
        return None


CALLEE_RESOLUTIONS: tuple[CalleeResolution, ...] = (
    OwnClass(),
    InstanceMethod(),
    ParentMethod(),
    AttributeMethod(),
    ParameterMethod(),
    InferredReceiverMethod(),
    NamedCallee(),
)
"""
The built-in resolutions, the first giving a call a target deciding it.
"""


@dataclass(frozen=True)
class CalleeResolutions:
    """
    The ways a call may reach its callee, tried in order.
    """

    ways: tuple[CalleeResolution, ...] = CALLEE_RESOLUTIONS
    """
    The resolutions, the first giving a call a target deciding it.
    """

    def target(self, function: ast.expr, scope: CallScope) -> CallTarget | None:
        """
        :param function: The called expression of a call.
        :param scope: What the code around the call tells.
        :return: The target of the first resolution giving one, ``None`` when none does.
        """
        return next(
            (
                found
                for resolution in self.ways
                if (found := resolution.target(function, scope)) is not None
            ),
            None,
        )
