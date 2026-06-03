#!/usr/bin/env bash
#
# Start/check an OpenVPN profile for Kali/HTB runs and write shell env exports.
# This script owns VPN setup; Python does not configure or manage networking.
#
# Usage:
#   ./scripts/config_vpn.sh path/to/profile.ovpn [tun0]
#   source .pentestagent-vpn.env
#
set -euo pipefail

usage() {
  printf 'Usage: %s path/to/profile.ovpn [vpn_interface]\n' "$0" >&2
  printf 'Example: %s machines_us-3.ovpn tun0\n' "$0" >&2
}

bad() {
  printf '[fail] %s\n' "$1" >&2
  exit 1
}

start_openvpn() {
  local -a openvpn_args=(
    --config "$VPN_CONFIG"
    --daemon pentestagent-vpn
    --writepid /tmp/pentestagent-openvpn.pid
  )

  if [ "$(id -u)" -eq 0 ]; then
    openvpn "${openvpn_args[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    sudo openvpn "${openvpn_args[@]}"
  else
    bad "sudo not found and current user is not root; run as root or install sudo"
  fi
}

VPN_CONFIG="${1:-}"
VPN_IFACE="${2:-tun0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT/.pentestagent-vpn.env"

if [ -z "$VPN_CONFIG" ]; then
  usage
  exit 2
fi

case "$VPN_CONFIG" in
  /*) ;;
  *) VPN_CONFIG="$(pwd)/$VPN_CONFIG" ;;
esac

[ -f "$VPN_CONFIG" ] || bad "VPN config not found: $VPN_CONFIG"
command -v openvpn >/dev/null 2>&1 || bad "openvpn not found on PATH"
command -v ip >/dev/null 2>&1 || bad "ip command not found on PATH"

if ip link show "$VPN_IFACE" >/dev/null 2>&1; then
  printf '[ ok ] VPN interface already exists: %s\n' "$VPN_IFACE"
else
  printf '[....] Starting OpenVPN with interface expectation: %s\n' "$VPN_IFACE"
  start_openvpn
fi

for _ in $(seq 1 45); do
  if ip link show "$VPN_IFACE" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

ip link show "$VPN_IFACE" >/dev/null 2>&1 || bad "VPN interface did not appear: $VPN_IFACE"

LHOST="$(ip -4 addr show "$VPN_IFACE" | awk '/inet / {print $2; exit}' | cut -d/ -f1)"
[ -n "$LHOST" ] || bad "Could not resolve IPv4 address for $VPN_IFACE"

cat > "$ENV_FILE" <<EOF
export PENTEST_VPN_INTERFACE="$VPN_IFACE"
export PENTEST_LHOST="$LHOST"
EOF

printf '[ ok ] VPN interface: %s\n' "$VPN_IFACE"
printf '[ ok ] LHOST: %s\n' "$LHOST"
printf '[ ok ] Wrote %s\n' "$ENV_FILE"
printf '\nRun this in your shell before preflight/agent runs:\n'
printf '  source %s\n' "$ENV_FILE"
