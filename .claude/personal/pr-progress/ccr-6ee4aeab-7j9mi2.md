Resolve at 72161178 (main at 64146fad merged in at d7360166; merge probe clean).

- 58a76a3f: review-triage-mark-viewed.yml installs from a clone of the workspace, with a test.
- 72161178: CI's pytest jobs failed at 58a76a3f in eight distributions run alone. BasstlerProject reads basstler-github's metadata instead of the meta-package's (test changed with the owner's approval); basstler-core requires the cyclopts it imports; review-triage's dev group lists hub. Reproduced CI's loop locally: all pass except hub's 43 browser launches.
- CI at 72161178 is not read; Windows, Python 3.12 and the hub's browser tests are not checked. No upstream is named; nothing is stacked on this branch.
