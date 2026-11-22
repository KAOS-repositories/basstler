Resolve at b5112caa (main at 64146fad merged in at d7360166; merge probe clean).

- 72161178: Linux CI passed (pytest 3.12 and 3.13, ruff); all four Windows shards failed.
- b5112caa: the Windows loop no longer counts pytest's exit 5 (a shard holding none of a distribution's tests) as a failure, with a test; the executable-bit test skips on Windows; the pip call assertion compares the configuration's own uv path. Both test edits approved by the owner. Linux checks pass; Windows is not run here.
- CI at b5112caa is not read. The PR was out of draft when I pushed; I left it as it was. No upstream is named; nothing is stacked on this branch.
