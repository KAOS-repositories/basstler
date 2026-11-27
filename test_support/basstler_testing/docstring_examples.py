"""
The examples written in docstrings, run as tests so each shows the output its code
gives.
"""

from __future__ import annotations

import ast
import doctest
import importlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from basstler.locations import WorkspaceLocation
from basstler.text_file import TextFile

from basstler_testing.constants.paths import DatasetLocation

# %% one example


@dataclass(frozen=True)
class DocstringExample:
    """
    The examples of one docstring, with the namespace of the module they are written in.
    """

    test: doctest.DocTest
    """
    The examples, as :mod:`doctest` runs them.
    """

    def assert_holds(self) -> None:
        """
        :raises AssertionError: If an example gives other output than it shows, with
            :mod:`doctest`'s report of each difference.
        """
        report: list[str] = []
        runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
        result = runner.run(self.test, out=report.append, clear_globs=False)
        assert result.failed == 0, "".join(report)

    def __str__(self) -> str:
        """
        :return: Where the docstring is, naming the test case.
        """
        return f"{self.test.name}:{self.test.lineno}"


# %% the examples of a source tree


@dataclass(frozen=True)
class SourceTree:
    """
    A directory of importable modules, whose docstrings' examples are collected.
    """

    directory: Path
    """
    The directory of the package the modules belong to.
    """

    package: str
    """
    The dotted name the directory is imported as.
    """

    excluded: tuple[Path, ...] = ()
    """
    Directories below it holding files other than its modules, such as snippets.
    """

    @classmethod
    def of_distribution(cls, test_file: str) -> SourceTree:
        """
        :param test_file: A test module of a distribution, as its ``__file__``.
        :return: The distribution's part of the ``basstler`` package.
        """
        distribution = next(
            directory
            for directory in Path(test_file).resolve().parents
            if (directory / "pyproject.toml").is_file()
        )
        source = distribution / WorkspaceLocation.PACKAGE_SOURCE
        return cls(source, source.name)

    @classmethod
    def of_test_support(cls) -> SourceTree:
        """
        :return: The helpers the suites of several distributions share.
        """
        directory = Path(__file__).resolve().parent
        return cls(directory, directory.name, (DatasetLocation.DIRECTORY,))

    def examples(self) -> list[DocstringExample]:
        """
        :return: The examples of every docstring that holds one, in a stable order.
        """
        return [
            example
            for path in sorted(self.directory.rglob("*.py"))
            if not any(path.is_relative_to(excluded) for excluded in self.excluded)
            and ">>>" in TextFile(path).read()
            for example in self.examples_in(path)
        ]

    def examples_in(self, path: Path) -> Iterator[DocstringExample]:
        """
        :param path: A module below the directory holding at least one example.
        :return: The examples of each of its docstrings, an attribute's included.
        """
        relative = path.relative_to(self.directory).with_suffix("")
        module_name = ".".join((self.package, *relative.parts))
        module = importlib.import_module(module_name)
        parser = doctest.DocTestParser()
        for owner, docstring in DocumentedName.all_in(
            ast.parse(TextFile(path).read()), module_name
        ):
            if ">>>" not in docstring.value:
                continue
            yield DocstringExample(
                parser.get_doctest(
                    docstring.value,
                    dict(vars(module)),
                    owner,
                    str(path),
                    docstring.lineno,
                )
            )


# %% the docstrings of a module's source


class DocumentedName:
    """
    Finds the docstrings of a module's source, an attribute's included, which a running
    module keeps no trace of.
    """

    @classmethod
    def all_in(
        cls, node: ast.Module | ast.ClassDef | ast.FunctionDef, qualified_name: str
    ) -> Iterator[tuple[str, ast.Constant]]:
        """
        :param node: A module, class or function.
        :param qualified_name: Its dotted name.
        :return: Each docstring below it, beside the dotted name of what it documents.
        """
        body = node.body
        for index, statement in enumerate(body):
            if isinstance(statement, ast.ClassDef | ast.FunctionDef):
                yield from cls.all_in(statement, f"{qualified_name}.{statement.name}")
                continue
            if not cls.is_docstring(statement):
                continue
            if index == 0:
                yield qualified_name, statement.value
                continue
            target = cls.assigned_name(body[index - 1])
            if target is not None:
                yield f"{qualified_name}.{target}", statement.value

    @staticmethod
    def is_docstring(statement: ast.stmt) -> bool:
        """
        :return: Whether *statement* is a bare string.
        """
        return (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )

    @staticmethod
    def assigned_name(statement: ast.stmt) -> str | None:
        """
        :return: The one name *statement* assigns, or ``None`` when it assigns none.
        """
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            return statement.target.id
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            return statement.targets[0].id
        return None
