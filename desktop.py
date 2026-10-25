"""Guided release launcher. Merely importing it never starts DHCP or downloads."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

import e3200_helper as helper

TFTPD_URL = "https://github.com/PJO2/tftpd64/releases/download/v4.74/tftpd64_portable_v4.74.zip"
TFTPD_ZIP_SHA = "3ad38a71c0d7d42915429f8f02945e27bcf88161ad1028980d1364af8f76bf22"
TFTPD_EXE_SHA = "43a8a79001510fa969ae31521aef550ff4c9c7771e903792b60a499ecf48b388"
MAX_DOWNLOAD = 20 * 1024 * 1024


def prepare_environment():
    """Restore system library lookup before executing external OS programs."""
    if not getattr(sys, "frozen", False):
        return
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    elif sys.platform.startswith("linux"):
        original = os.environ.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = original
    os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"


def capture(arguments):
    result = subprocess.run(arguments, text=True, capture_output=True, timeout=20,
                            check=True, env={**os.environ, "LC_ALL": "C"})
    return result.stdout


def data_directory():
    if sys.platform == "win32":
        base = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "E3200-DHCP-Helper"


def private_directory(path):
    if path.is_symlink():
        raise RuntimeError("The helper's local folder cannot be a symbolic link.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise RuntimeError("The helper's local path must be a folder.")
    if os.name != "nt":
        os.chmod(path, 0o700)


def save_configuration(path, config):
    config = helper.validate_config(config, require_confirmed=True)
    private_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(config, output, indent=2)
        output.write("\n")
    if os.name != "nt":
        os.chmod(path, 0o600)


def discover_adapters():
    """Read active physical Ethernet configuration; do not change it."""
    adapters = []
    if sys.platform == "win32":
        script = r"""
$ErrorActionPreference='Stop'
@(
Get-NetAdapter -Physical | Where-Object {
    $_.Status -eq 'Up' -and ([string]$_.MediaType -eq '802.3' -or [int]$_.NdisPhysicalMedium -eq 14)
} | ForEach-Object {
    $a=$_; $c=Get-NetIPConfiguration -InterfaceIndex $a.ifIndex
    foreach($ip in $c.IPv4Address) {
        if($c.IPv4DefaultGateway.NextHop) {
            [pscustomobject]@{interface=$a.Name; ip=$ip.IPAddress; prefix=$ip.PrefixLength; gateway=$c.IPv4DefaultGateway.NextHop}
        }
    }
}
) | ConvertTo-Json -Compress
"""
        text = capture(["powershell.exe", "-NoProfile", "-Command", script]).strip()
        values = json.loads(text) if text else []
        adapters = values if isinstance(values, list) else [values]
    elif sys.platform == "darwin":
        ports = capture(["/usr/sbin/networksetup", "-listallhardwareports"])
        route = capture(["/sbin/route", "-n", "get", "default"])
        gateway = re.search(r"^\s*gateway:\s*([0-9.]+)\s*$", route, re.M)
        default_nic = re.search(r"^\s*interface:\s*(\S+)", route, re.M)
        for block in ports.split("\n\n"):
            nic = re.search(r"^Device: (\S+)", block, re.M)
            if not nic or re.search(r"Hardware Port:.*(?:Wi-Fi|AirPort)", block, re.I):
                continue
            if not gateway or not default_nic or nic[1] != default_nic[1]:
                continue
            output = capture(["/sbin/ifconfig", nic[1]])
            if "status: active" not in output:
                continue
            for address, mask in re.findall(r"^\s+inet ([0-9.]+) netmask (0x[0-9a-fA-F]+|[0-9.]+)", output, re.M):
                mask = str(ipaddress.IPv4Address(int(mask, 16))) if mask.startswith("0x") else mask
                prefix = ipaddress.IPv4Network("0.0.0.0/" + mask).prefixlen
                adapters.append(dict(interface=nic[1], ip=address, prefix=prefix, gateway=gateway[1]))
    elif sys.platform.startswith("linux"):
        values = json.loads(capture(["ip", "-j", "-4", "address", "show"]))
        routes = json.loads(capture(["ip", "-j", "-4", "route", "show", "default"]))
        for value in values:
            nic = value["ifname"]
            device = Path("/sys/class/net") / nic
            if not (device / "device").exists() or (device / "wireless").exists():
                continue
            gateway = next((r.get("gateway") for r in routes if r.get("dev") == nic), None)
            if not gateway:
                continue
            for address in value.get("addr_info", []):
                if address.get("scope") == "global":
                    adapters.append(dict(interface=nic, ip=address["local"], prefix=address["prefixlen"], gateway=gateway))
    return [a for a in adapters if not ipaddress.IPv4Address(a["ip"]).is_link_local]


def default_extender_ip(adapter):
    subnet = ipaddress.IPv4Network(f"{adapter['ip']}/{adapter['prefix']}", strict=False)
    candidate = subnet.broadcast_address - 5
    if candidate <= subnet.network_address or str(candidate) in {adapter["ip"], adapter["gateway"]}:
        raise ValueError("Choose an extender address manually for this subnet.")
    return str(candidate)


def configuration_from_answers(adapter, mac, address, lease):
    mac = mac.strip().replace("-", ":").upper()
    return helper.validate_config({
        "extender_mac": mac, "extender_ip": address.strip(), "server_ip": adapter["ip"],
        "gateway": adapter["gateway"], "dns": adapter["gateway"],
        "subnet_mask": str(ipaddress.IPv4Network("0.0.0.0/" + str(adapter["prefix"])).netmask),
        "interface": adapter["interface"], "lease_minutes": lease, "address_plan_confirmed": True,
    }, require_confirmed=True)


def verified_tftpd_payload(contents):
    if hashlib.sha256(contents).hexdigest() != TFTPD_ZIP_SHA:
        raise ValueError("Official download checksum did not match; nothing was installed.")
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        entries = [e for e in archive.infolist() if Path(e.filename).name.lower() == "tftpd64.exe"]
        if len(entries) != 1 or entries[0].file_size > MAX_DOWNLOAD:
            raise ValueError("The portable download does not contain the expected executable.")
        executable = archive.read(entries[0])
    if hashlib.sha256(executable).hexdigest() != TFTPD_EXE_SHA:
        raise ValueError("Executable checksum did not match; nothing was installed.")
    return executable


def obtain_windows_engine(directory):
    destination = directory / "vendor" / "tftpd64.exe"
    if destination.is_symlink():
        raise RuntimeError("The DHCP program path cannot be a symbolic link.")
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == TFTPD_EXE_SHA:
        return destination
    print("\nWindows uses Tftpd64 v4.74, downloaded separately from its official release.")
    print(TFTPD_URL)
    print("Its archive and executable checksums will both be verified.")
    if input("Download the required program now? Type YES: ").strip() != "YES":
        raise RuntimeError("Download cancelled. The helper was not started.")
    request = urllib.request.Request(TFTPD_URL, headers={"User-Agent": "E3200-DHCP-Helper"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.geturl().startswith("https://"):
            raise RuntimeError("The download redirected to an insecure address.")
        contents = response.read(MAX_DOWNLOAD + 1)
    if len(contents) > MAX_DOWNLOAD:
        raise RuntimeError("Unexpected download size; nothing was installed.")
    payload = verified_tftpd_payload(contents)
    private_directory(destination.parent)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload)
    return destination


def self_test():
    adapter = dict(interface="Ethernet", ip="192.168.1.240", prefix=24, gateway="192.168.1.1")
    c = configuration_from_answers(adapter, "AA:BB:CC:DD:EE:FF", "192.168.1.250", 60)
    assert "dhcp-ignore=tag:!e3200" in helper.render_dnsmasq(c)
    assert "PoolSize=0" in helper.render_tftpd(c)
    if sys.platform == "win32":
        assert (Path(__file__).parent / "windows/Start-Helper.ps1").is_file()
    print("Packaged launcher self-test passed. No network, DHCP, or administrator action performed.")
    return 0


def wizard():
    if sys.platform == "win32" and not ctypes.windll.shell32.IsUserAnAdmin():
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Use an Administrator terminal when running the source wizard.")
        status = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "--wizard", None, 1)
        if status <= 32:
            raise RuntimeError("Administrator approval was cancelled or unavailable.")
        return 0
    print("\nE3200 DHCP Helper — guided setup\n")
    print("Your existing router stays in charge of Internet access.")
    print("Keep this computer awake and this helper open while serving.\n")
    path = data_directory() / "config.local.json"
    config = None
    if path.exists():
        old = helper.load_config(path, require_confirmed=True)
        print(f"Saved extender: {old['extender_ip']}   Adapter: {old['interface']}")
        if input("Press Enter to use saved settings, or type SETUP to change them: ").strip().upper() != "SETUP":
            config = old
    if config is None:
        adapters = discover_adapters()
        if not adapters:
            raise RuntimeError("No active physical Ethernet connection with an IPv4 gateway was found. Check the cable and connection first.")
        for index, adapter in enumerate(adapters, 1):
            print(f"  {index}. {adapter['interface']} — this computer {adapter['ip']}, router {adapter['gateway']}")
        choice = input("Choose the connected home-network adapter [1]: ").strip() or "1"
        if not choice.isdigit() or not 1 <= int(choice) <= len(adapters):
            raise ValueError("Choose an adapter number shown above.")
        adapter = adapters[int(choice) - 1]
        mac = input("Enter the E3200's MAC address (six pairs, such as AA:BB:CC:DD:EE:FF): ")
        suggested = default_extender_ip(adapter)
        print("\nAn address suggestion is NOT a check that the address is unused.")
        address = input(f"Unused address set aside for the E3200 [{suggested}]: ").strip() or suggested
        print("\nLease duration: 1 = one hour (test renewal), 2 = 24 hours, 3 = 365 days")
        print("A long lease does not remove the need for the helper after renewal or a restart.")
        durations = {"1": 60, "2": 1440, "3": 525600}
        duration = input("Choose a lease [1]: ").strip() or "1"
        if duration not in durations:
            raise ValueError("Choose lease option 1, 2, or 3.")
        candidate = configuration_from_answers(adapter, mac, address, durations[duration])
        print(f"\nE3200: {candidate['extender_mac']} -> {candidate['extender_ip']}")
        print(f"This computer: {candidate['server_ip']}   Router/DNS: {candidate['gateway']}")
        print("Before continuing, check existing leases and static devices.")
        print("Keep this computer's address stable and exclude/reserve both addresses")
        print("so the router cannot give either address to a different device.")
        print("Keep the main router's normal DHCP enabled. Stop any previous helper.")
        if input("Type YES only after checking this address plan: ").strip() != "YES":
            raise RuntimeError("Address plan was not confirmed. Nothing was started.")
        save_configuration(path, candidate)
        config = candidate
        print(f"Settings saved privately in {path}")
    print(f"\nAfter the extender accepts its lease, open https://{config['extender_ip']}")
    print("Use the extender's administrator login to open its network settings.\n")
    if sys.platform == "win32":
        binary = obtain_windows_engine(data_directory())
        script = Path(__file__).resolve().parent / "windows/Start-Helper.ps1"
        return subprocess.call(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-File", str(script), "-Config", str(path), "-Program", str(binary)])
    executable = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
    if os.geteuid() == 0:
        return helper.run_helper(config)
    print("Administrator access is needed to serve this extender. Your password may be requested.")
    return subprocess.call(["sudo", *executable, "--serve", "--config", str(path)])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open-and-follow E3200 helper setup")
    parser.add_argument("--wizard", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--engine-test", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--config")
    arguments = parser.parse_args(argv)
    prepare_environment()
    interactive = not (arguments.self_test or arguments.engine_test or arguments.serve)
    try:
        if arguments.self_test:
            return self_test()
        if arguments.engine_test:
            c = dict(helper.EXAMPLE_CONFIG, interface="en0")
            return subprocess.run([helper._dnsmasq_binary(), "--test", "--conf-file=-"],
                                  input=helper.render_dnsmasq(c), text=True, check=False).returncode
        if arguments.serve:
            if not arguments.config:
                raise ValueError("A saved configuration is required.")
            return helper.run_helper(helper.load_config(arguments.config, require_confirmed=True))
        if sys.platform == "win32" and not ctypes.windll.shell32.IsUserAnAdmin():
            # The elevated setup gets its own console; do not leave a second
            # unelevated setup window waiting for input.
            interactive = False
        return wizard()
    except KeyboardInterrupt:
        print("\nStopping. Check that this helper's process and window have closed.")
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"\nHelper stopped: {error}", file=sys.stderr)
        print("See the Downloads guide or Troubleshooting page in the repository.", file=sys.stderr)
        return 1
    finally:
        if interactive and sys.stdin.isatty():
            try:
                input("\nPress Enter to close this setup window.")
            except (EOFError, KeyboardInterrupt):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
