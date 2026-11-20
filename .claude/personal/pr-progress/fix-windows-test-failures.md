## Plan
- Make the Windows CI job finish (it timed out at ~82% at 958944a1) and fix the Windows failures it names.

## Done
- b3b95932: Windows job split into 4 shards (`--shard-index`/`--shard-count` from strategy.job-index/job-total), Defender real-time scanning off, TEMP on runner.temp, timeout 20 min, `--durations=20`.
- b3b95932: portability checks 162 s -> ~50 s (no tree copy, one walk for calls/returns, names resolved only in files that spell them).
- 2c02c51a: main merged (probe clean vs 34892a38); full suite green on Linux locally.

## Next
- Read the sharded Windows run for 2c02c51a (not read yet): fix each failure it names, test-first.
- PR stays ready for review (the user marked it ready), so each push runs the Windows job.
