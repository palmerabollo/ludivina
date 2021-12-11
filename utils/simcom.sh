#!/bin/bash

set -euo pipefail

IFACE="wwan0"

echo "DHCP request to get IP"
/usr/sbin/udhcpc --retries=5 --now -i $IFACE
echo "Route all traffic to wwan0"
/usr/sbin/route add -net 0.0.0.0 $IFACE
