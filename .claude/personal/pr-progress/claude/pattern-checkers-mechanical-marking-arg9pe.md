Plan:
- Wait for the owner on the 7 open review threads of #222, among them whether the remaining modules move onto TextFile.

Done:
- TextFile (core) and PythonSourceFile; SourceFixer.fix_module(source_file); specifications_of_module.
- basstler.code_modification.syntax: ConstantName, ExpressionSyntax, CallSyntax, after krracker's LibCSTNodeFactory.
- KeywordArgumentFix and CallLackingKeywordArgument; UTF8EncodingFix subclasses it.
- Fixed the UTF-8 violation the main merge brought onto #220 (afbd09d8) and merged it in.
- 2865 passed, 1 skipped at 59f12519; pushed; replies posted; description updated.
- Carried into claude/loving-maxwell-s1y58z (pushed) and claude/kind-bohr-db512e (d8a64776, renames adopted, 2897 passed).

Next:
- Act on the owner's answers to the open threads.
- #223 (ccr-6ee4aeab-7j9mi2) still conflicts; where text_file, syntax and source_file land in packages/ is its owner's call (text_file belongs in core).
