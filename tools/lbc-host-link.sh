#!/bin/sh
# lbc-host-link.sh - point a host NIC at a LubanCat AMP board over a direct cable.
#
#   sudo tools/lbc-host-link.sh up   [iface] [host-ip] [prefix]
#   sudo tools/lbc-host-link.sh down [iface]
#
# Defaults: iface=enp195s0  host-ip=192.168.77.1  prefix=24
# Board side default (buildroot overlay 30-eth0-static): eth0 = 192.168.77.2/24.
#
# 'up' takes the interface away from NetworkManager and gives it a static address;
# 'down' flushes it and hands it back to NetworkManager.
set -eu

action=${1:-}
iface=${2:-enp195s0}
host_ip=${3:-192.168.77.1}
prefix=${4:-24}
board_ip=${BOARD_IP:-192.168.77.2}
nm_conf=/etc/NetworkManager/conf.d/99-unmanaged-lubancat.conf

usage() {
	echo "usage: $0 {up|down} [iface] [host-ip] [prefix]" >&2
	exit 2
}

require_root() {
	[ "$(id -u)" = 0 ] || {
		echo "error: run as root (try: sudo $0 $*)" >&2
		exit 1
	}
}

nm_set_managed() {
	# $1 = yes|no
	command -v nmcli >/dev/null 2>&1 || return 0
	nmcli device set "$iface" managed "$1" 2>/dev/null || true
	nmcli general reload 2>/dev/null || true
}

case "$action" in
up)
	require_root "$@"
	mkdir -p /etc/NetworkManager/conf.d
	cat > "$nm_conf" <<EOF
# Created by zenith/tools/lbc-host-link.sh - keep $iface unmanaged.
[keyfile]
unmanaged-devices=interface-name:$iface
EOF
	nm_set_managed no
	ip link set "$iface" up
	ip addr replace "$host_ip/$prefix" dev "$iface"
	if ! grep -qE "^$board_ip[[:space:]].*\bboard\b" /etc/hosts; then
		printf '%s\tboard lubancat\n' "$board_ip" >> /etc/hosts
	fi
	echo "OK: $iface = $host_ip/$prefix (NetworkManager unmanaged)"
	echo "    board should answer at $board_ip  ->  ssh root@$board_ip"
	;;
down)
	require_root "$@"
	ip addr flush dev "$iface" 2>/dev/null || true
	rm -f "$nm_conf"
	nm_set_managed yes
	sed -i -E "/^$board_ip[[:space:]].*\bboard\b/d" /etc/hosts 2>/dev/null || true
	echo "OK: $iface returned to NetworkManager"
	;;
*)
	usage
	;;
esac
