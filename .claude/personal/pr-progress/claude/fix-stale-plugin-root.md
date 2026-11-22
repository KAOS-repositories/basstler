## Plan
- Bug fix for a stale BASSTLER_PLUGIN_ROOT after Claude Code renames the plugin directory
- Reproduce, failing test, then make the env file re-resolve the directory

## Done
- Reproduced (exit 127 after rename), failing test, fix in plugin/hooks/session-start.sh
- Hook tests (243) and ruff pass; draft PR #292 labelled bug

## Next
- Check CI on #292
- Open: what the `~g2` suffix means and why the restarted session kept the old path
