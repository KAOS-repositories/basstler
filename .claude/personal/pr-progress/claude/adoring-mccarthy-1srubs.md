Plan
- Each distribution but the meta-package runs its tests with only its own requirements
Done
- Helpers split by layer, crossing tests moved, dev groups trimmed, production file moves (see #287)
- main merged at 8e056c3f; merge probe CLEAN
- CI at 13b3bef9 failed 57 plan item_bootstrap tests (save-plan.sh needs the whole package); moved to the meta-package at 90bbe8dd
- Local runs now unset BASSTLER_* (they had hidden the failure); all pass alone except hub's unchecked browser tests
Next
- Read CI at 90bbe8dd
