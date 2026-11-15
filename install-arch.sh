#!/bin/bash
set -e

# ==============================================================================
# HP USB Fingerprint Mouse - Arch Linux Driver Installer
# Hardware IDs:
#   - Optical HID Mouse: 03f0:4b4a
#   - Fingerprint Sensor: 06cb:00c3 (Synaptics Metallica MIS)
# Firmware Payload: 6_07f_hp_mis_qm.xpfwext
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===================================================================="
echo " Installing HP USB Fingerprint Mouse Driver on Arch Linux"
echo "===================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This installation script must be run as root."
    echo "    Please run: sudo ./install-arch.sh"
    exit 1
fi

echo "[1/6] Installing dependencies via pacman..."
pacman -Sy --noconfirm --needed \
    python \
    python-cryptography \
    python-dbus \
    python-gobject \
    python-pyusb \
    python-yaml \
    fprintd \
    usbutils

echo "[2/6] Masking stock fprintd..."
systemctl stop fprintd.service 2>/dev/null || true
systemctl mask fprintd.service 2>/dev/null || true

echo "[3/6] Installing driver files to /usr/local/lib/hp-fingerprint-mouse/..."
INSTALL_LIB="/usr/local/lib/hp-fingerprint-mouse"
mkdir -p "${INSTALL_LIB}"
mkdir -p "${INSTALL_LIB}/firmware"

cp -r "${SCRIPT_DIR}/validitysensor" "${INSTALL_LIB}/"
cp -r "${SCRIPT_DIR}/openfprintd" "${INSTALL_LIB}/"
cp "${SCRIPT_DIR}/python-validity-dbus/dbus-service" "${INSTALL_LIB}/"
cp "${SCRIPT_DIR}/openfprintd-dbus/open-fprintd" "${INSTALL_LIB}/"
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" "${INSTALL_LIB}/firmware/"

chmod +x "${INSTALL_LIB}/dbus-service"
chmod +x "${INSTALL_LIB}/open-fprintd"
cp "${SCRIPT_DIR}/test_hp_mouse.py" /usr/bin/hp-mouse-test
chmod +x /usr/bin/hp-mouse-test

echo "[4/6] Deploying sensor firmware to system runtime directories..."
mkdir -p /var/lib/python-validity/firmware/
mkdir -p /usr/share/python-validity/firmware/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /var/lib/python-validity/firmware/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /usr/share/python-validity/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /usr/share/python-validity/firmware/
chmod 644 /var/lib/python-validity/firmware/6_07f_hp_mis_qm.xpfwext
chmod 644 /usr/share/python-validity/6_07f_hp_mis_qm.xpfwext

echo "[5/6] Installing D-Bus and udev rules..."
cp "${SCRIPT_DIR}/net.reactivated.Fprint.conf" /etc/dbus-1/system.d/
cp "${SCRIPT_DIR}/io.github.uunicorn.Fprint.conf" /etc/dbus-1/system.d/
systemctl reload dbus 2>/dev/null || true

cp "${SCRIPT_DIR}/70-hp-fingerprint-mouse.rules" /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger --attr-match=idVendor=06cb --attr-match=idProduct=00c3 || udevadm trigger

echo "[6/6] Enabling and starting systemd background services..."
cp "${SCRIPT_DIR}/open-fprintd.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/python3-validity.service" /etc/systemd/system/

systemctl daemon-reload
rm -f /var/run/python-validity/backoff 2>/dev/null || true
systemctl reset-failed python3-validity.service 2>/dev/null || true
systemctl enable open-fprintd.service
systemctl enable python3-validity.service
systemctl restart open-fprintd.service
systemctl restart python3-validity.service

echo ""
echo "===================================================================="
echo " Installation Complete on Arch Linux!"
echo "===================================================================="
echo ""
echo "Service Status:"
systemctl status open-fprintd.service --no-pager --lines=2 || true
echo "---"
systemctl status python3-validity.service --no-pager --lines=2 || true
echo ""
echo "Diagnostic check:"
echo "   hp-mouse-test"
echo ""
echo "Enroll your fingerprint:"
echo "   fprintd-enroll"
echo ""
echo "Verify enrollment:"
echo "   fprintd-verify"
echo ""
echo "Note for Arch Linux PAM authentication (sudo / login):"
echo "To enable fingerprint login in sudo on Arch, add this line to /etc/pam.d/sudo:"
echo "   auth sufficient pam_fprintd.so"
echo "To enable fingerprint login in SDDM/GDM/system-local-login, add the same line"
echo "to the top of the auth section in /etc/pam.d/system-local-login"
echo "===================================================================="
