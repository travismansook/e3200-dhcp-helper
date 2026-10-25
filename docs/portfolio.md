# Engineering case study

**Project:** E3200 DHCP Helper<br>
**Focus:** Protocol troubleshooting, configuration validation and cross-platform automation<br>
**Stack:** Python, PowerShell, Bash, dnsmasq, Tftpd64, systemd, GitHub Actions

## Problem

An E3200 client repeatedly rejected DHCP offers after a router change. A status-page address alone did not establish whether the client had accepted a current lease.

## Investigation

The original logs showed **1,902 offers rejected for missing option 60**. A scoped Windows helper supplied that field, after which **18 offers were rejected for missing option 125**. Supplying both fields using a synthetic legacy gateway identity resulted in an observed DHCPREQUEST, DHCPACK and bound lease.

An initial address-conflict hypothesis was revised when fresh DHCP/ARP evidence did not support it. The investigation followed the protocol exchange and current mappings instead of relying on retained status fields.

## Engineering decisions

- Serve one configured MAC while preserving the existing router's normal DHCP service.
- Validate addresses, subnet, interface and lease duration before serving.
- Generate inspectable engine configuration rather than build another DHCP server.
- Support native Windows PowerShell plus a shared Python path for macOS/Linux.
- Separate offline checks from live evidence, with Linux runtime marked experimental.
- Keep local configurations, binaries and raw household logs out of the repository.

## Result and evidence

The Windows prototype obtained an accepted lease. A later full-day device-log sample contained **4,320 gateway-loss reports at 0%**, followed by 51 early the next day. These are sampled gateway observations, not a continuous or end-to-end benchmark.

The generalized public implementation requires platform-specific field validation. See the [validation record](validation.md) and current CI results.

## Résumé wording

**E3200 DHCP Helper — Python, PowerShell, Bash, DHCP, GitHub Actions**

- Diagnosed vendor-option rejection in DHCP negotiation and reproduced successful E3200 lease acquisition using a MAC-scoped compatibility profile.
- Developed configurable Windows, macOS and experimental Linux workflows with input validation, synthetic regression tests, reversible operation and setup documentation.

Use wording that reflects what you personally verified. Do not describe untested Linux runtime or prototype observations as universal compatibility.

## Development notes

Implementation and documentation were developed with AI assistance. Protocol claims were checked against primary documentation, upstream behavior and the observed DHCP exchange.
