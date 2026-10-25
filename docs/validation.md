# Validation record

This record separates observed behavior from tests of the generalized implementation.

## Original field evidence

| Stage | Observation |
|---|---|
| Original-router offers | 1,902 rejected for missing option 60 |
| First helper trial | 18 rejected for missing option 125 |
| Both supplied | DHCPREQUEST, DHCPACK and a bound lease observed |

A later log sample covering the full **2026-10-24 device-clock date** contained **4,320 gateway-loss reports at 0%**, with no recorded backhaul reset. The first approximately 17 minutes of October 25 contained another **51 reports at 0%**.

The logs did not include a timezone offset. These were periodic gateway checks, not continuous capture or an end-to-end latency/throughput benchmark. Only aggregate findings are published.

## Implementation matrix

| Component | Evidence | Remaining validation |
|---|---|---|
| Original Windows prototype / Tftpd64 v4.74 | Accepted lease and finite gateway-check observations | One observed setup |
| Public Windows launcher | Configuration, scope and offline checks | Runtime/cleanup on each supported Windows setup |
| Original Mac configuration | dnsmasq 2.93 syntax acceptance | Accepted-duration and runtime evidence |
| Public macOS runner | Shared configuration/rendering/preflight code | Generalized runner field trial |
| Linux foreground/service paths | Experimental implementation and offline checks | Target runtime field trial |
| Management controller, IPv6, multiple extenders | Outside this project's validated scope | No support inferred |

See CI for its actual current results. Automated checks and successful syntax parsing are separate from a live network result.

The initial public [GitHub Actions run](https://github.com/travismansook/e3200-dhcp-helper/actions/runs/40164419112) passed all six jobs: Python tests on Windows, macOS and Ubuntu (including Python 3.10 and 3.14), native Windows PowerShell and modern PowerShell checks, plus the dnsmasq configuration parser. Tests use synthetic input and do not start a DHCP server.

## Validate your installation

Record OS, DHCP engine and extender firmware without exposing private identifiers:

1. Review the address plan and rendered one-MAC configuration.
2. Verify the selected wired interface and stable helper address.
3. Start one helper and confirm unrelated clients still use the router.
4. Observe the extender's accepted lease and fresh MAC/address mapping.
5. Observe renewal with the initial 60-minute lease.
6. Restart the extender during a controlled test and verify reacquisition.
7. Verify host reboot/service startup if persistence is enabled.
8. Stop normally and inspect process/firewall cleanup.
9. Record gateway-check duration, coverage and gaps separately.

Use synthetic or sanitized data publicly. Describe exactly what was measured.
