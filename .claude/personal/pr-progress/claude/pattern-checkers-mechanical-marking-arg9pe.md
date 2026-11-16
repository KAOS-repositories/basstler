Plan:
- Answer the 18 owner review threads of #222 (read at 8b6656f6).
- TextFile (core) reads and writes UTF-8; PythonSourceFile parses it; SourceFixer.fix_module takes the file.
- Rename FixableChecker.specifications to specifications_of_module.
- basstler.code_modification.syntax: ConstantName, ExpressionSyntax and CallSyntax wrapper classes, after krracker's LibCSTNodeFactory (cited as krrood).
- KeywordArgumentFix: a general fix adding or substituting one keyword argument; UTF8EncodingFix subclasses it.
- Keep AppliedAction.inverse a field (owner agreed); reply on the question threads.

Done:
- Stack pass; merge probe clean at 8b6656f6; blocker recorded.

Next:
- Tests first, then the refactor, ruff, docformatter, code-rules check, full suite, push, replies.
