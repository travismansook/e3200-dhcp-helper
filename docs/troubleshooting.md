# DHCP troubleshooting

Trace the exchange in order: discover, offer, request, acknowledgment. Align client/helper timestamps and check the retained period.

| Symptom | Next check |
|---|---|
| Placeholder or plan error | Replace examples and independently verify addresses before confirmation |
| Interface/address mismatch | Confirm the chosen wired interface's current IPv4/mask and stable assignment |
| UDP 67 busy | Identify the existing process and stop the previous helper normally |
| No offer | Check the interface, physical link, host firewall and extender backhaul |
| Missing vendor-class identifier | Confirm option 60 reaches the client |
| Missing `vivso` | Verify the complete option 125 payload |
| Accepted lease, gateway unreachable | Compare gateway/subnet and fresh MAC/address mappings |
| No renewal after host sleep | Restore helper availability and inspect the exchange |
| Unrelated clients affected | Stop the helper and review its scope and address plan |

## Current address versus retained configuration

A status-page address can be retained configuration. A stale ARP entry or failed browser connection alone does not prove an address conflict. Compare an accepted lease, a fresh MAC/address mapping and a reachability test.

Excluding an address from a dynamic pool does not invalidate an existing lease immediately. Check current bindings and manual assignments before using it.

An offer alone is not acceptance. Look for DHCPREQUEST, DHCPACK and a client-side bound state.

## Read-only log analysis

```sh
python3 tools/analyze_bhm.py YOUR_LOCAL_LOG --date YYYY-MM-DD
```

The JSON output reports retained coverage, numeric gateway-loss samples, explicit backhaul state events and backward clock steps. It does not execute log text or send network traffic.

A diagnostic function named `bh_disconnected` may occur beside successful checks; the analyzer counts explicit state markers instead. A device clock reset can combine different sessions under the same date. Inspect the source records and analyzer limits.

## Clean retry

Stop the helper through its normal controls. Confirm its process and temporary Windows firewall rule are gone before launching another instance. Keep the router's normal DHCP enabled.

Resolve failed preflight checks instead of enabling a general pool or starting another responder. Long leases do not eliminate renewal or reacquisition.

Public issues should contain short sanitized exchanges or synthetic reproductions. Keep real identifiers, raw logs, captures and local configuration private.
