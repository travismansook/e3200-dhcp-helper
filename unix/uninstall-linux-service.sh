#!/usr/bin/env bash
# Removes only this installer's service registration; preserves configuration.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo "Run this script with sudo." >&2
    exit 1
fi
/usr/bin/python3 - <<'PY'
from pathlib import Path
import subprocess
unit = Path("/etc/systemd/system/e3200-dhcp-helper.service")
marker = "# Managed by e3200-dhcp-helper Ubuntu installer.\n"
if unit.is_symlink() or not unit.is_file() or not unit.read_text(encoding="utf-8").startswith(marker):
    raise SystemExit("No service owned by this installer was found; nothing was changed.")
subprocess.run(["/usr/bin/systemctl", "disable", "--now", unit.name], check=True)
if subprocess.run(["/usr/bin/systemctl", "is-active", "--quiet", unit.name]).returncode == 0:
    raise SystemExit("The service is still active; its unit was preserved.")
unit.unlink()
subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True)
print("Removed this helper's service registration. Other DHCP services and firewall rules were unchanged.")
print("Preserved: /etc/e3200-dhcp-helper/config.json")
print("Preserved: /usr/local/lib/e3200-dhcp-helper/e3200_helper.py")
print("Review those dedicated directories before removing them or reinstalling.")
PY
