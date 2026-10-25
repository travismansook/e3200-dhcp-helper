#!/usr/bin/env bash
# Read-only service/network/log inspection. Use sudo for complete process/log views.
set -uo pipefail
echo "Helper service:"
systemctl --no-pager --full status e3200-dhcp-helper.service || true
echo
echo "Current IPv4 addresses:"
ip -brief -4 address show
echo
echo "Current default routes:"
ip -4 route show default
echo
echo "UDP67 listeners:"
ss -H -lunp 'sport = :67'
echo
echo "Recent helper logs:"
journalctl --no-pager -u e3200-dhcp-helper.service -n 80
