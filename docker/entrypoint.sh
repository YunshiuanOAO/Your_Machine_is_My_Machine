#!/usr/bin/env bash
# Configure and launch sshd for the local Kali lab box.
set -e

# Generate host keys on first boot.
ssh-keygen -A

mkdir -p /root/.ssh
chmod 700 /root/.ssh

# Key-based login: if a public key was mounted, trust it.
if [ -f /tmp/authorized_keys ]; then
  cp /tmp/authorized_keys /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi

# Password fallback (lab convenience; port is bound to localhost only).
echo "root:${ROOT_PASSWORD:-kali}" | chpasswd

# Allow root login for this throwaway lab container.
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

echo "[entrypoint] sshd ready on container port 22 (root password: ${ROOT_PASSWORD:-kali})"
exec /usr/sbin/sshd -D -e
