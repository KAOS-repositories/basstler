## Plan
- Make the Windows CI job finish and pass.

## Done
- b3b95932: 4 shards, Defender off, TEMP on runner.temp, 20 min timeout; portability checks 162 s -> ~50 s. Windows run 44833340854 (2c02c51a) finished in ~10 min with 16 failures named.
- 864bace2: those 16 fixed - posix paths in tests, Windows drive root in entry-point approval, scripts dir for the console script, Windows skips for stubs Git Bash or Windows cannot reach and versioned interpreter names. Changed files pass on Linux.

## Next
- Read the Windows run for 864bace2 when the user says it finished; the curl-fallback skip rests on a likely, unverified cause (Git Bash puts its own curl first).
- #222 restack conflicts with this branch's checker speed-ups: the user decides.
