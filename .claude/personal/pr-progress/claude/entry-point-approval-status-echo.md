### Plan
- Resolve review thread r4619570035/r4619583656: build every regex in src/ from named parts.
- Add `basstler.regular_expression`: a StrEnum of named atoms and a composable `RegularExpression` class (user chose in-house over pregex).
- Rewrite `entry_point_approval.py`'s patterns first (the thread's file), then every other pattern in src/.
- Add a code rule plus checker that rejects raw regex literals outside that module.
- Tests first, then ruff, docformatter, `basstler code-rules check`, pytest.
### Done
- Stack pass: branch restacked onto main acc38242 (merge commit 9a4358c4). Merge probe at e7b1e8a: clean. CI at e7b1e8a: all 7 checks green.
- No upstream configured, so there is no upstream review to read.
### Next
- Write the module's tests.
