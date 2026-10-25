# How it works

## Follow the DHCP exchange

The E3200 client received offers but did not request a lease. Its logs identified a missing vendor-class identifier. Supplying option 60 exposed a second requirement, option 125, called `vivso` in the client log.

| Stage | Original observation |
|---|---|
| Existing router | 1,902 offers rejected for missing option 60 |
| First helper trial | 18 offers rejected for missing option 125 |
| Both supplied | DHCPREQUEST, DHCPACK and a bound lease followed on Windows |

These observations describe one setup, not requirements for every DHCP client or firmware version. [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html) defines DHCP's offer/request/acknowledgment exchange.

## Compatibility profile

| Field | Value |
|---|---|
| Option 60 | Eight ASCII bytes: `ARCADYAN` |
| Option 125 | 38-byte vendor-identifying payload |
| Enterprise number | 3561, Broadband Forum |
| Gateway identity | OUI, synthetic serial and product class `G3100` |

The profile emulates a legacy gateway identity. Its serial is fictitious. It contains no real device serial, network password or management-server URL. Identity information may still influence firmware behavior; it is not vendor approval or a management controller.

[RFC 3925](https://www.rfc-editor.org/rfc/rfc3925.html) defines the enterprise-number framing. [Broadband Forum TR-069 Annex F](https://www.broadband-forum.org/pdfs/tr-069-1-6-1.pdf) describes the gateway identity suboptions.

## Scope

On macOS/Linux, dnsmasq receives a separate configuration: DNS disabled, a static-only range, one tagged MAC mapping, and an ignore rule for unmatched clients. On Windows, Tftpd64 receives DHCP-only service selection, zero dynamic pool size and one static mapping. The Windows wrapper also checks existing registry mappings.

This is a second, narrowly scoped DHCP responder. MAC matching is a scope control, not authentication. Correct address exclusions and one running helper remain necessary.

The existing router remains gateway and DNS by default. The helper handles lease negotiation; it does not relay normal Internet traffic.

## Lease duration

Use **60 minutes** first so renewal can be observed. After successful testing, **24 hours** is an operational option for an always-available helper.

A **365-day lease** is an advanced choice. It can reduce routine renewals but does not guarantee operation after an extender restart, lease loss or early request. Changing the server's setting does not retroactively change an already accepted lease.

DHCP clients normally renew around half the lease duration, although server timers and client behavior can differ. Inspect the accepted lease and actual renewal rather than assuming the configured duration was accepted.

See the [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html) and [Tftpd64 DHCP source at v4.74](https://github.com/PJO2/tftpd64/blob/v4.74/src/_services/bootpd.c).
