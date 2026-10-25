"""MAC-restricted E3200 DHCP compatibility helper; Python 3.10+, stdlib only.

Offline check/render commands open no sockets. The emulated G3100 identity is
experimental compatibility data, not authentication or official mesh support.
"""
from __future__ import annotations

import argparse
import contextlib
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

OPTION60 = "ARCADYAN"
OPTION125_HEX = "00:00:0d:e9:21:04:06:38:38:30:33:35:35:05:10:47:30:30:30:30:30:30:30:30:30:30:30:30:30:30:30:06:05:47:33:31:30:30"
FIELDS = {"extender_mac", "extender_ip", "server_ip", "gateway", "dns",
          "subnet_mask", "interface", "lease_minutes", "address_plan_confirmed"}
EXAMPLE_CONFIG = {
    "extender_mac": "AA:BB:CC:DD:EE:FF",
    "extender_ip": "192.168.1.250", "server_ip": "192.168.1.240",
    "gateway": "192.168.1.1", "dns": "192.168.1.1",
    "subnet_mask": "255.255.255.0", "interface": "REPLACE_WITH_INTERFACE",
    "lease_minutes": 60, "address_plan_confirmed": False,
}


class ConfigError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a nonempty string")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ConfigError(f"{field} contains a control character")
    return value.strip()


def _ipv4(value: Any, field: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.IPv4Address(_text(value, field))
    except ipaddress.AddressValueError as exc:
        raise ConfigError(f"{field} must be an IPv4 address") from exc
    if address.is_multicast or address.is_unspecified or address.is_loopback or address.is_reserved or int(address) < 0x01000000:
        raise ConfigError(f"{field} must be a usable unicast IPv4 address")
    return address


def validate_config(config: dict, require_confirmed: bool = False) -> dict:
    if not isinstance(config, dict):
        raise ConfigError("configuration must be a JSON object")
    missing, unknown = FIELDS - config.keys(), config.keys() - FIELDS
    if missing or unknown:
        raise ConfigError(f"missing fields: {sorted(map(str, missing))}; unknown fields: {sorted(map(str, unknown))}")
    result = dict(config)
    mac = _text(config["extender_mac"], "extender_mac")
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", mac):
        raise ConfigError("extender_mac must contain six colon-separated hexadecimal octets")
    octets = bytes.fromhex(mac.replace(":", ""))
    if octets[0] & 1 or octets == bytes(6):
        raise ConfigError("extender_mac must be a nonzero unicast MAC")
    result["extender_mac"] = ":".join(f"{v:02X}" for v in octets)
    addresses = {key: _ipv4(config[key], key) for key in ("extender_ip", "server_ip", "gateway", "dns")}
    try:
        mask = ipaddress.IPv4Address(_text(config["subnet_mask"], "subnet_mask"))
    except ipaddress.AddressValueError as exc:
        raise ConfigError("subnet_mask must be a dotted IPv4 netmask") from exc
    inverse = int(mask) ^ 0xFFFFFFFF
    if inverse & (inverse + 1):
        raise ConfigError("subnet_mask must contain contiguous leading one bits")
    network = ipaddress.IPv4Network(f"{addresses['server_ip']}/{mask}", strict=False)
    if not 1 <= network.prefixlen <= 30:
        raise ConfigError("subnet_mask must leave usable IPv4 host addresses")
    lan = [addresses[k] for k in ("server_ip", "extender_ip", "gateway")]
    if len(set(lan)) != 3:
        raise ConfigError("server_ip, extender_ip and gateway must be different")
    if any(a not in network or a in (network.network_address, network.broadcast_address) for a in lan):
        raise ConfigError("server_ip, extender_ip and gateway must be usable hosts in the same subnet")
    if addresses["dns"] in (network.network_address, network.broadcast_address):
        raise ConfigError("dns cannot be the local subnet network or broadcast address")
    interface = _text(config["interface"], "interface")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.: -]{0,63}", interface):
        raise ConfigError("interface contains unsupported characters")
    if "REPLACE" in interface.upper() or interface.upper() in {"YOUR_INTERFACE", "INTERFACE"}:
        raise ConfigError("replace the interface placeholder with the actual adapter name")
    lease = config["lease_minutes"]
    if type(lease) is not int or not 2 <= lease <= 525600:
        raise ConfigError("lease_minutes must be an integer from 2 through 525600")
    if type(config["address_plan_confirmed"]) is not bool:
        raise ConfigError("address_plan_confirmed must be a JSON boolean")
    if require_confirmed and not config["address_plan_confirmed"]:
        raise ConfigError("confirm helper/extender addresses are reserved or excluded, checked for conflicts, and other helpers stopped")
    result.update({key: str(value) for key, value in addresses.items()})
    result.update(subnet_mask=str(mask), interface=interface)
    return result


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_config(path: str | Path, require_confirmed: bool = False) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle, object_pairs_hook=_unique_object)
    return validate_config(data, require_confirmed=require_confirmed)


def render_dnsmasq(config: dict) -> str:
    c = validate_config(config)
    lease = f"{c['lease_minutes']}m"
    return "\n".join([
        "# E3200 helper: DHCP only, one exact MAC, no global configuration imports.",
        "port=0", "no-resolv", "no-hosts",
        f"interface={c['interface']}", "except-interface=lo", "bind-interfaces",
        "dhcp-lease-max=1",
        f"dhcp-range={c['extender_ip']},static,{c['subnet_mask']},{lease}",
        f"dhcp-host={c['extender_mac']},id:*,set:e3200,{c['extender_ip']},{lease}",
        "dhcp-ignore=tag:!e3200",
        f"dhcp-option=tag:e3200,option:router,{c['gateway']}",
        f"dhcp-option=tag:e3200,option:dns-server,{c['dns']}",
        f"dhcp-option-force=tag:e3200,60,{OPTION60}",
        "# Experimental legacy gateway identity with a fictitious serial.",
        f"dhcp-option-force=tag:e3200,125,{OPTION125_HEX}",
        "log-dhcp", "log-facility=-", "",
    ])


def render_tftpd(config: dict) -> str:
    c = validate_config(config)
    lines = [
        "; E3200 helper: DHCP only, zero dynamic pool, one static MAC.",
        "[TFTPD32]", "Services=4", f"DHCP LocalIP={c['server_ip']}",
        "DHCP Ping=0", "DHCP Double Answer=0", "PersistantLeases=0",
        "UnicastBOOTP=0", "Enable IPv4=1", "Enable IPv6=0", "UseEventLog=0",
        "TftpLogFile=", "SaveSyslogFile=", "",
        "[DHCP]", f"IP_Pool={c['extender_ip']}", "PoolSize=0",
        f"Lease (minutes)={c['lease_minutes']}", f"Gateway={c['gateway']}",
        f"Mask={c['subnet_mask']}", f"DNS={c['dns']}", "DNS2=", "WINS=",
        "BootFile=", "Option42=", "Option120=", "DomainName=", "Lease_NumLeases=0",
        "AddOptionNumber1=60", f"AddOptionValue1=s {OPTION60}",
        "AddOptionNumber2=125", f"AddOptionValue2=x {OPTION125_HEX}",
    ]
    for number in range(3, 11):
        lines.extend([f"AddOptionNumber{number}=0", f"AddOptionValue{number}="])
    lines.extend([f"{c['extender_mac']}={c['extender_ip']}", ""])
    return "\n".join(lines)


def _tool(name: str) -> str:
    for directory in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
        path = Path(directory) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError(f"required system tool is missing: {name}")


def _command(arguments: list[str], ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    process = subprocess.run(arguments, text=True, capture_output=True, timeout=15, check=False,
                             env={**os.environ, "LC_ALL": "C"})
    if process.returncode not in ok:
        raise RuntimeError(f"{Path(arguments[0]).name} failed: {process.stderr.strip() or process.stdout.strip()}")
    return process


def _preflight(config: dict, allow_wifi: bool = False) -> None:
    c = validate_config(config, require_confirmed=True)
    nic = c["interface"]
    expected_prefix = ipaddress.IPv4Network(f"0.0.0.0/{c['subnet_mask']}").prefixlen
    if sys.platform.startswith("linux"):
        device = Path("/sys/class/net") / nic
        if not (device / "device").exists() or (device / "type").read_text().strip() != "1":
            raise RuntimeError("select an actual physical Ethernet interface")
        if (device / "wireless").exists():
            raise RuntimeError("this Linux launcher requires wired Ethernet")
        if (device / "carrier").read_text().strip() != "1":
            raise RuntimeError("Ethernet has no link; verify cable and router port first")
        address_info = json.loads(_command([_tool("ip"), "-j", "-4", "address", "show", "dev", nic]).stdout)
        addresses = [a for entry in address_info for a in entry.get("addr_info", []) if a.get("scope") == "global"]
        if len(addresses) != 1 or addresses[0].get("local") != c["server_ip"] or addresses[0].get("prefixlen") != expected_prefix:
            raise RuntimeError("the selected interface must already have exactly server_ip/subnet_mask; no address was changed")
        routes = json.loads(_command([_tool("ip"), "-j", "-4", "route", "show", "default", "dev", nic]).stdout)
        if not any(route.get("gateway") == c["gateway"] for route in routes):
            raise RuntimeError("the selected Ethernet interface must already use the configured main gateway")
        if _command([_tool("ss"), "-H", "-lun", "sport = :67"]).stdout.strip():
            raise RuntimeError("UDP67 is already in use; no existing service will be replaced")
        profiles = Path("/sys/kernel/security/apparmor/profiles")
        if profiles.exists() and re.search(r"(^|/)(usr/sbin/dnsmasq|dnsmasq)([ (]|$)", profiles.read_text(), re.M):
            raise RuntimeError("a dnsmasq AppArmor profile is loaded; review runtime-path permissions without disabling AppArmor")
    elif sys.platform == "darwin":
        ports = _command([_tool("networksetup"), "-listallhardwareports"]).stdout
        blocks = [b for b in ports.split("\n\n") if re.search(rf"^Device: {re.escape(nic)}\s*$", b, re.M)]
        if len(blocks) != 1:
            raise RuntimeError("select an actual hardware interface, such as en0 or en5")
        wireless = bool(re.search(r"Hardware Port:.*(?:Wi-Fi|AirPort)", blocks[0], re.I))
        if wireless and not allow_wifi:
            raise RuntimeError("Wi-Fi requires explicit --allow-wifi; Ethernet is preferred")
        output = _command([_tool("ifconfig"), nic]).stdout
        if "status: active" not in output:
            raise RuntimeError("the selected interface has no active link")
        addresses = re.findall(r"^\s+inet ([0-9.]+) netmask (0x[0-9a-fA-F]+|[0-9.]+)", output, re.M)
        expected_mask = int(ipaddress.IPv4Address(c["subnet_mask"]))
        if len(addresses) != 1:
            raise RuntimeError("the selected interface must have exactly one IPv4 address")
        address, mask = addresses[0]
        numeric_mask = int(mask, 16) if mask.startswith("0x") else int(ipaddress.IPv4Address(mask))
        if address != c["server_ip"] or numeric_mask != expected_mask:
            raise RuntimeError("the interface must already match server_ip/subnet_mask; no address was changed")
        route = _command([_tool("route"), "-n", "get", "default"]).stdout
        if not re.search(rf"^\s*gateway:\s*{re.escape(c['gateway'])}\s*$", route, re.M) or not re.search(rf"^\s*interface:\s*{re.escape(nic)}\s*$", route, re.M):
            raise RuntimeError("the default route must use the selected interface and configured main gateway")
        listener = _command([_tool("lsof"), "-nP", "-iUDP:67"], ok=(0, 1))
        if listener.stdout.strip() or listener.stderr.strip():
            raise RuntimeError("UDP67 is busy or its availability could not be verified")
    else:
        raise RuntimeError("run is supported on Linux and macOS; Windows uses the separate launcher")


def _dnsmasq_binary() -> str:
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        bundled = Path(sys.executable).resolve().with_name("dnsmasq")
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
        raise RuntimeError("the bundled DHCP engine is missing; extract a complete macOS release again")
    for name in ("/usr/sbin/dnsmasq", "/usr/local/sbin/dnsmasq", "/opt/homebrew/sbin/dnsmasq"):
        if Path(name).is_file() and os.access(name, os.X_OK):
            return name
    raise RuntimeError("dnsmasq is missing; install dnsmasq-base on Ubuntu or dnsmasq with Homebrew on macOS")


@contextlib.contextmanager
def _runtime(config: dict):
    import grp
    import pwd
    account = pwd.getpwnam("nobody")
    group = grp.getgrgid(account.pw_gid).gr_name
    # macOS TMPDIR can have private ancestors that nobody cannot traverse.
    with tempfile.TemporaryDirectory(prefix="e3200-dhcp-", dir="/tmp") as directory:
        root = Path(directory)
        os.chmod(root, 0o711)
        state = root / "state"
        state.mkdir(mode=0o700)
        os.chown(state, account.pw_uid, account.pw_gid)
        configuration = root / "dnsmasq.conf"
        configuration.write_text(render_dnsmasq(config), encoding="utf-8")
        os.chmod(configuration, 0o600)
        arguments = [_dnsmasq_binary(), f"--conf-file={configuration}",
                     f"--pid-file={state / 'dnsmasq.pid'}", f"--dhcp-leasefile={state / 'leases'}",
                     "--user=nobody", f"--group={group}"]
        yield arguments


def run_helper(config: dict, allow_wifi: bool = False, preflight_only: bool = False) -> int:
    if sys.platform not in ("linux", "darwin") or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise RuntimeError("run/preflight requires root on Linux or macOS; use sudo")
    c = validate_config(config, require_confirmed=True)
    _preflight(c, allow_wifi=allow_wifi)
    with _runtime(c) as arguments:
        _command([*arguments, "--test"])
        if preflight_only:
            print("Preflight passed; no DHCP daemon was started.")
            return 0
        print(f"Starting E3200-only helper on {c['interface']}; main gateway remains {c['gateway']}.", flush=True)
        process = None
        stopping = False
        deadline = None

        def stop(_number, _frame):
            nonlocal stopping, deadline
            stopping = True
            deadline = time.monotonic() + 5
            if process is not None and process.poll() is None:
                process.terminate()

        previous = {number: signal.signal(number, stop) for number in (signal.SIGINT, signal.SIGTERM)}
        try:
            process = subprocess.Popen([*arguments, "--keep-in-foreground"])
            if stopping:
                process.terminate()
            while process.poll() is None:
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    if deadline is not None and time.monotonic() >= deadline:
                        process.kill()
            return 0 if stopping else process.returncode
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for number, handler in previous.items():
                signal.signal(number, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initial = commands.add_parser("init", help="write an example config without overwriting an existing file")
    initial.add_argument("--output", default="config.local.json")
    for name in ("check", "render", "run"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True)
        if name == "render":
            command.add_argument("--format", required=True, choices=("dnsmasq", "tftpd"))
            command.add_argument("--output")
        elif name == "run":
            command.add_argument("--allow-wifi", action="store_true", help="explicit macOS Wi-Fi opt-in; delivery is not guaranteed")
            command.add_argument("--preflight-only", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            example = Path(__file__).with_name("config.example.json")
            contents = example.read_text(encoding="utf-8") if example.exists() else json.dumps(EXAMPLE_CONFIG, indent=2) + "\n"
            descriptor = os.open(arguments.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(contents)
            print(f"Created {arguments.output}; edit placeholders and verify the address plan before running.")
            return 0
        config = load_config(arguments.config, require_confirmed=arguments.command == "run")
        if arguments.command == "check":
            print("Configuration is valid. This offline check does not test network readiness.")
            return 0
        if arguments.command == "render":
            contents = render_dnsmasq(config) if arguments.format == "dnsmasq" else render_tftpd(config)
            if arguments.output:
                descriptor = os.open(arguments.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    output.write(contents)
            else:
                print(contents, end="")
            return 0
        return run_helper(config, arguments.allow_wifi, arguments.preflight_only)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
