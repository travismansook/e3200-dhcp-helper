# Third-party notices

This repository contains original scripts, configuration generation, documentation and synthetic tests. Ready-to-open releases include a Python runtime. Mac downloads also include a build of unmodified dnsmasq source, its full corresponding source archive, build instructions and license notices. Windows obtains Tftpd64 separately from upstream on first use; Ubuntu packages depend on the distribution's dnsmasq-base package.

Release downloads include Python's license and PyInstaller's license/bootloader exception in their licenses folder. The build workflow pins PyInstaller and records its version, Python version, architecture and source commit in build-info.json. External components retain their own licenses.

## dnsmasq

Maintained by Simon Kelley and contributors. The [official project page](https://thekelleys.org.uk/dnsmasq/doc.html) states GPL version 2 or version 3 at the user's discretion. Consult `COPYING` and `COPYING-v3` in the distribution.

[Project/source](https://thekelleys.org.uk/dnsmasq/doc.html) · [Manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html)

Invoking dnsmasq does not relicense it under this project's MIT license.

## Tftpd64

Developed by Philippe Jounin and contributors. The Windows workflow targets the separately downloaded portable v4.74 executable.

Upstream notices differ: the [tagged readme](https://github.com/PJO2/tftpd64/blob/v4.74/readme.txt) and [DHCP source header](https://github.com/PJO2/tftpd64/blob/v4.74/src/_services/bootpd.c) identify EUPL, while the same tag's [license.md](https://github.com/PJO2/tftpd64/blob/v4.74/license.md) contains GPLv2 text. This notice records the discrepancy without resolving it or asserting an EUPL version.

[Repository](https://github.com/PJO2/tftpd64) · [Pinned release](https://github.com/PJO2/tftpd64/releases/tag/v4.74)

Retain the downloaded distribution's notices. Obtain clarification from upstream before redistributing its code or binaries. No Tftpd64 executable is bundled here.

## Protocol references and names

[RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html), [RFC 3925](https://www.rfc-editor.org/rfc/rfc3925.html) and [Broadband Forum TR-069 Annex F](https://www.broadband-forum.org/pdfs/tr-069-1-6-1.pdf) informed the explanation and profile. They are linked, not redistributed.

Verizon, Arcadyan, E3200, CHR30A and G3100 identify relevant equipment. This project is independent and is not affiliated with or endorsed by their owners.
