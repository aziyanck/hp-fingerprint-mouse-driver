#!/bin/bash
set -e

echo "===================================================================="
echo " Uninstalling HP USB Fingerprint Mouse Driver"
echo "===================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This uninstallation script must be run as root."
    echo "    Please run: sudo ./uninstall.sh"
    exit 1
fi

echo "[1/5] Stopping and disabling custom services..."
systemctl stop python3-validity.service 2>/dev/null || true
systemctl stop open-fprintd.service 2>/dev/null || true
systemctl disable python3-validity.service 2>/dev/null || true
systemctl disable open-fprintd.service 2>/dev/null || true

echo "[2/5] Removing systemd unit files..."
rm -f /etc/systemd/system/python3-validity.service
rm -f /etc/systemd/system/open-fprintd.service
systemctl daemon-reload

echo "[3/5] Restoring standard fprintd service..."
systemctl unmask fprintd.service 2>/dev/null || true
systemctl start fprintd.service 2>/dev/null || true

echo "[4/5] Removing udev rules and D-Bus policies..."
rm -f /etc/udev/rules.d/70-hp-fingerprint-mouse.rules
udevadm control --reload-rules
udevadm trigger

rm -f /etc/dbus-1/system.d/net.reactivated.Fprint.conf
rm -f /etc/dbus-1/system.d/io.github.uunicorn.Fprint.conf
systemctl reload dbus 2>/dev/null || true

echo "[5/5] Removing driver binaries..."
rm -rf /usr/local/lib/hp-fingerprint-mouse/

echo "===================================================================="
echo " Uninstallation Complete."
echo "===================================================================="
