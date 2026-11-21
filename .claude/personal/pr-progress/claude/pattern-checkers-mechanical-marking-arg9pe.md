## Plan
- Resolve what stalled #222: it conflicted with main (7 files, then 2 more after main moved) and Windows CI failed in `tests/test_text_file.py` (newline translation) plus 13 tests main's #220 already fixed.
- Keep the libcst design of #222 and give it main's import-aware matching instead of keeping both `SourceModule` and `PositionedModule`.

## Done
- Merged main twice (`d08c4065` is in the head): `PositionedModule.metadata`, `CodePattern` matching with it, `ReferenceTo` (imports resolve `subprocess`/`shutil.rmtree` under any name); `SourceModule` and its tests removed. main's datasets for imported names pass on the patterns.
- `TextFile` reads and writes the UTF-8 bytes, so line endings stay as stored; the `TextFile` fix declares that change. Tests first: a CRLF read test failed before the change.
- Re-applied `TextFile` to the code main brought (`plan/model.py`, `plan/item_bootstrap/documents.py`, `plan/handover.py`, `plan/manifest_tools.py`, `code_rules/address_building.py`) with `code-rules fix`.

## Next
- Read CI at the pushed head; the Windows run is the one that matters.
- Mark ready again only when you say so.
