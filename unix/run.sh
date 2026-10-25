#!/usr/bin/env bash
# Foreground launcher; creates no network settings or firewall rules.
set -euo pipefail
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$script_dir/../e3200_helper.py" run "$@"
