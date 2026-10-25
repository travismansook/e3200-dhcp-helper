"""Build release downloads on native CI runners; never run a live DHCP server."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VERSION = (ROOT / "VERSION").read_text().strip()
DNSMASQ_URL = "https://thekelleys.org.uk/dnsmasq/dnsmasq-2.93.tar.gz"
DNSMASQ_SHA = "cc967771abdafeb43d10db18932d6b59fd4bed2c69c22acf8cb96aff6920d55f"
START_TEXT = """E3200 DHCP Helper {version}

1. Extract the complete download; keep the program folder next to the launcher.
2. Open the launcher and follow the questions. No Python installation or JSON editing is needed.
3. Enter your E3200 MAC address, choose its reserved/excluded IP, and review your address plan.
4. Keep the computer awake and helper running. After lease acceptance, open the extender IP in your browser.

Windows downloads its pinned Tftpd64 dependency from the official release on first use, with permission.
Mac releases include dnsmasq, its full corresponding source archive, and license notices.
Ubuntu packages use the distribution's dnsmasq-base dependency and install no background service.

These community builds are unsigned. Windows or macOS may ask you to review an unfamiliar download.
Linux support is experimental. Read the Downloads guide for platform limits and startup errors.

Full guide: https://github.com/travismansook/e3200-dhcp-helper/blob/main/docs/downloads.md
"""


def run(arguments, **kwargs):
    subprocess.run([str(a) for a in arguments], check=True, **kwargs)


def download(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def add_notices(destination):
    notices = destination / "licenses"
    notices.mkdir(parents=True)
    for name in ("LICENSE", "THIRD-PARTY-NOTICES.md"):
        shutil.copy2(ROOT / name, notices / name)
    python_license = next((p for p in (Path(sys.base_prefix) / "LICENSE.txt",
                                      Path(sysconfig.get_path("stdlib")) / "LICENSE.txt") if p.is_file()), None)
    contents = python_license.read_bytes() if python_license else download(
        f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE")
    (notices / "Python-LICENSE.txt").write_bytes(contents)
    distribution = importlib.metadata.distribution("pyinstaller")
    for entry in distribution.files or []:
        if entry.name.lower().startswith(("copying", "license")):
            source = distribution.locate_file(entry)
            if source.is_file():
                shutil.copy2(source, notices / ("PyInstaller-" + entry.name))
    (destination / "START-HERE.txt").write_text(START_TEXT.format(version=VERSION), encoding="utf-8")
    (destination / "build-info.json").write_text(json.dumps({
        "version": VERSION, "source_commit": os.environ.get("GITHUB_SHA", "local"),
        "python": platform.python_version(), "pyinstaller": importlib.metadata.version("pyinstaller"),
        "system": platform.system(), "architecture": platform.machine(),
    }, indent=2) + "\n")


def build_mac_engine(program, notices):
    archive = download(DNSMASQ_URL)
    if hashlib.sha256(archive).hexdigest() != DNSMASQ_SHA:
        raise RuntimeError("dnsmasq source checksum did not match")
    source_archive = notices / "dnsmasq-2.93.tar.gz"
    source_archive.write_bytes(archive)
    source_root = ROOT / "build/dnsmasq"
    source_root.mkdir(parents=True)
    with tarfile.open(source_archive) as source:
        source.extractall(source_root, filter="data")
    source_dir = source_root / "dnsmasq-2.93"
    run(["make", "COPTS=-DNO_GETTEXT -DNO_LUA -DNO_DBUS -DNO_UBUS -DNO_IDN -DNO_DNSSEC",
         "CFLAGS=-O2 -D__APPLE_USE_RFC_3542"], cwd=source_dir)
    shutil.copy2(source_dir / "src/dnsmasq", program / "dnsmasq")
    (program / "dnsmasq").chmod(0o755)
    run(["codesign", "--force", "--sign", "-", program / "dnsmasq"])
    for name in ("COPYING", "COPYING-v3"):
        shutil.copy2(source_dir / name, notices / ("dnsmasq-" + name))
    (notices / "dnsmasq-BUILD.txt").write_text(
        "Unmodified upstream dnsmasq 2.93 source is included alongside this notice.\n"
        "Source: " + DNSMASQ_URL + "\nSHA-256: " + DNSMASQ_SHA + "\n"
        "Built with the native macOS Clang toolchain:\n"
        "make 'COPTS=-DNO_GETTEXT -DNO_LUA -DNO_DBUS -DNO_UBUS -DNO_IDN -DNO_DNSSEC' "
        "'CFLAGS=-O2 -D__APPLE_USE_RFC_3542'\n"
        "The helper invokes this executable separately; original helper code remains MIT licensed.\n"
    )


def zip_tree(folder, output):
    # Keep executable bits and symlinks used by PyInstaller's native bundles.
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder.parent).as_posix()
            if path.is_symlink():
                info = zipfile.ZipInfo(relative)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, os.readlink(path))
            elif path.is_file():
                archive.write(path, relative)


def main():
    os.chdir(ROOT)
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    build = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
             "--name", "E3200Helper", "--add-data", f"{ROOT / 'windows/Start-Helper.ps1'}{os.pathsep}windows",
             str(ROOT / "desktop.py")]
    run(build)
    built = ROOT / "dist/E3200Helper"
    binary = built / ("E3200Helper.exe" if sys.platform == "win32" else "E3200Helper")
    run([binary, "--self-test"])
    if sys.platform == "win32":
        # Verify first-run dependency availability and both pinned hashes.
        # Do not bundle or execute this upstream executable.
        import desktop
        desktop.verified_tftpd_payload(download(desktop.TFTPD_URL))
    label = "Windows-x64" if sys.platform == "win32" else (
        "macOS-AppleSilicon" if platform.machine() == "arm64" else "macOS-Intel")
    if sys.platform.startswith("linux"):
        package = ROOT / "build/debian"
        application = package / "usr/lib/e3200-dhcp-helper"
        shutil.copytree(built, application / "program", symlinks=True)
        add_notices(application)
        desktop_dir = package / "usr/share/applications"
        desktop_dir.mkdir(parents=True)
        (desktop_dir / "e3200-dhcp-helper.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=E3200 DHCP Helper\n"
            "Comment=Guided E3200 address compatibility helper\n"
            "Exec=/usr/lib/e3200-dhcp-helper/program/E3200Helper --wizard\n"
            "Terminal=true\nCategories=Network;Utility;\n")
        control = package / "DEBIAN"
        control.mkdir()
        (control / "control").write_text(
            f"Package: e3200-dhcp-helper\nVersion: {VERSION}\nArchitecture: amd64\n"
            "Maintainer: Travis Mansook <162916263+travismansook@users.noreply.github.com>\n"
            "Depends: dnsmasq-base, iproute2, sudo, libc6 (>= 2.35)\n"
            "Section: net\nPriority: optional\n"
            "Description: Guided single-extender DHCP compatibility helper (experimental)\n"
            " Includes Python runtime. Starts only when the user opens the launcher.\n")
        for directory in package.rglob("*"):
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(0o755)
        artifact = output / "E3200-Helper-Ubuntu-amd64.deb"
        run(["dpkg-deb", "--root-owner-group", "--build", package, artifact])
        run(["dpkg-deb", "--info", artifact])
        run(["sudo", "dpkg", "-i", artifact])
        run(["/usr/lib/e3200-dhcp-helper/program/E3200Helper", "--self-test"])
    else:
        folder = ROOT / "build" / ("E3200-Helper-" + label)
        shutil.copytree(built, folder / "program", symlinks=True)
        add_notices(folder)
        if sys.platform == "win32":
            (folder / "Open E3200 Helper.cmd").write_text(
                '@echo off\r\n"%~dp0program\\E3200Helper.exe" --wizard\r\n', newline="")
        else:
            build_mac_engine(folder / "program", folder / "licenses")
            run([folder / "program/E3200Helper", "--engine-test"])
            launcher = folder / "Open E3200 Helper.command"
            launcher.write_text('#!/bin/bash\nset -eu\ncd -- "$(dirname -- "$0")"\n'
                                './program/E3200Helper --wizard\n')
            launcher.chmod(0o755)
        zip_tree(folder, output / ("E3200-Helper-" + label + ".zip"))
    print("Release download built and startup-tested; no DHCP server was started.")


if __name__ == "__main__":
    main()
