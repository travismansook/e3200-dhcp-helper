#!/usr/bin/env bash
# Experimental Ubuntu installer. Activation requires an explicit --start.
# No interface addresses, other DHCP services or firewall rules are changed.
set -euo pipefail
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ] || [ "$1" != "--config" ] || { [ "$#" -eq 3 ] && [ "$3" != "--start" ]; }; then
    echo "Usage: sudo bash unix/install-linux-service.sh --config /absolute/config.json [--start]" >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi
if [ ! -r /etc/os-release ]; then
    echo "This experimental installer supports Ubuntu only." >&2
    exit 1
fi
. /etc/os-release
if [ "$ID" != "ubuntu" ]; then
    echo "This experimental installer supports Ubuntu only." >&2
    exit 1
fi
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
module="$script_dir/../e3200_helper.py"
config="$2"
activation=""
if [ "$#" -eq 3 ]; then activation="$3"; fi
if ! command -v systemctl >/dev/null || [ ! -x /usr/bin/python3 ]; then
    echo "Ubuntu systemd and /usr/bin/python3 are required." >&2
    exit 1
fi
if [ ! -x /usr/sbin/dnsmasq ]; then
    echo "Install the DHCP binary first: sudo apt install dnsmasq-base" >&2
    exit 1
fi
/usr/bin/python3 - "$module" "$config" "$activation" <<'PY'
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or newer is required.")
module = Path(sys.argv[1]).resolve(strict=True)
configuration = Path(sys.argv[2]).resolve(strict=True)
activate = sys.argv[3] == "--start"
code_dir = Path("/usr/local/lib/e3200-dhcp-helper")
config_dir = Path("/etc/e3200-dhcp-helper")
unit = Path("/etc/systemd/system/e3200-dhcp-helper.service")
marker = "# Managed by e3200-dhcp-helper Ubuntu installer.\n"
api = runpy.run_path(str(module))
config = api["load_config"](configuration, require_confirmed=True)
if unit.exists() or unit.is_symlink():
    if unit.is_symlink() or not unit.is_file() or not unit.read_text().startswith(marker):
        raise SystemExit("An existing unit is not owned by this installer; unchanged.")
    if not activate:
        raise SystemExit("This helper is already installed. Review its files; use --start to activate or the uninstall script to remove its unit.")
    active = subprocess.run(["/usr/bin/systemctl", "is-active", "--quiet", unit.name]).returncode == 0
    if active:
        raise SystemExit("This helper is already active. Inspect its status instead of starting another instance.")
    installed = config_dir / "config.json"
    installed_api = runpy.run_path(str(code_dir / "e3200_helper.py"))
    installed_config = installed_api["load_config"](installed, require_confirmed=True)
    if installed_config != config:
        raise SystemExit("Installed configuration differs; review it rather than silently replacing it.")
    installed_api["run_helper"](installed_config, preflight_only=True)
else:
    for destination in (code_dir, config_dir):
        if destination.exists() or destination.is_symlink():
            raise SystemExit(f"{destination} already exists. Review it before reinstalling; no existing files were overwritten.")
    api["run_helper"](config, preflight_only=True)
    unit_text = marker + """[Unit]
Description=MAC-restricted E3200 DHCP compatibility helper (experimental)
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Group=root
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
ExecStart=/usr/bin/python3 /usr/local/lib/e3200-dhcp-helper/e3200_helper.py run --config /etc/e3200-dhcp-helper/config.json
Restart=on-failure
RestartSec=30
TimeoutStopSec=12
KillMode=mixed
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
"""
    code_dir.mkdir(mode=0o755)
    config_dir.mkdir(mode=0o700)
    try:
        with (code_dir / "e3200_helper.py").open("x", encoding="utf-8") as output:
            output.write(module.read_text(encoding="utf-8"))
        os.chmod(code_dir / "e3200_helper.py", 0o644)
        with (config_dir / "config.json").open("x", encoding="utf-8") as output:
            json.dump(config, output, indent=2)
            output.write("\n")
        os.chmod(config_dir / "config.json", 0o600)
        with unit.open("x", encoding="utf-8") as output:
            output.write(unit_text)
        os.chmod(unit, 0o644)
    except Exception:
        print("Installation did not complete. Inspect the dedicated helper paths before retrying.", file=sys.stderr)
        raise
subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True)
if activate:
    result = subprocess.run(["/usr/bin/systemctl", "enable", "--now", unit.name], check=False)
    if result.returncode:
        subprocess.run(["/usr/bin/systemctl", "disable", "--now", unit.name], check=False)
        raise SystemExit("Activation failed; automatic startup was disabled. Installed files remain for inspection.")
    print("Installed and enabled e3200-dhcp-helper.service; verify its journal and accepted lease.")
else:
    print("Installed e3200-dhcp-helper.service without enabling or starting it.")
    print("Review the unit and installed configuration before using --start.")
print("Firewall rules and main-router DHCP were unchanged.")
print("Check: sudo bash unix/check-linux.sh")
PY
