#!/bin/bash
# Stands in for `systemctl` on PATH: appends its arguments to STUB_SYSTEMCTL_LOG and
# exits with STUB_SYSTEMCTL_EXIT_CODE.
printf '%s\n' "$*" >> "${STUB_SYSTEMCTL_LOG}"
exit "${STUB_SYSTEMCTL_EXIT_CODE:-0}"
