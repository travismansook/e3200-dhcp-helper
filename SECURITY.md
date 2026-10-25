# Security and operational scope

Use this project on a LAN you own or administer. It starts a DHCP responder, so an incorrect address plan or general pool can disrupt other devices.

The intended configuration matches one extender MAC, disables dynamic allocation and advertises the existing router as gateway/DNS. Keep normal router DHCP enabled, exclude helper/extender addresses from its dynamic pool and run only one helper.

MAC matching is a scope control, not authentication. The synthetic gateway identity may influence information used by firmware. This is an independent interoperability profile, not vendor approval.

Administrator/root access is needed for privileged DHCP operation and platform setup. Inspect scripts before running them. Keep access local to the intended LAN and resolve preflight failures without weakening machine-wide protections.

## Private data

Local configuration, leases, diagnostics and packet captures can identify devices and the network. Logging is not encrypted by this project. Review data before sharing it.

Public issues should use synthetic or carefully sanitized examples. Remove real MACs, serials, hostnames, credentials, device IP addresses and private paths. Runtime files are ignored by Git; verify your staged files before publishing.

## Reporting vulnerabilities

Use **Security → Report a vulnerability** on the repository when available. Provide affected versions, a synthetic reproduction and the scope/impact. Avoid a public issue containing sensitive network data or an active exploit against another network.

If private reporting is unavailable, open an issue requesting a private channel without disclosing sensitive details. There is no guaranteed response time.

Stop the helper normally while a scope issue is investigated. Check cleanup and keep the router's normal DHCP available.
