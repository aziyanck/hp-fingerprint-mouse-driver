#!/bin/bash
set -e

# ==============================================================================
# HP USB Fingerprint Mouse - Ubuntu Linux Driver Installer
# Hardware IDs:
#   - Optical HID Mouse: 03f0:4b4a
#   - Fingerprint Sensor: 06cb:00c3 (Synaptics Metallica MIS)
# Firmware Payload: 6_07f_hp_mis_qm.xpfwext
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===================================================================="
echo " Installing HP USB Fingerprint Mouse Driver & Services on Ubuntu"
echo "===================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "[-] Error: This installation script must be run as root."
    echo "    Please run: sudo ./install.sh"
    exit 1
fi

echo "[1/7] Installing / verifying system dependencies..."
apt-get update -qq || true
apt-get install -y -qq \
    python3 \
    python3-cryptography \
    python3-yaml \
    python3-dbus \
    python3-gi \
    libpam-fprintd \
    fprintd \
    usbutils \
    udev || true

# Ensure pyusb is available
if ! python3 -c "import usb" 2>/dev/null; then
    echo "[*] Installing pyusb..."
    apt-get install -y -qq python3-usb || pip3 install --break-system-packages pyusb || true
fi

echo "[2/7] Configuring conflict mitigation with stock fprintd..."
# Stock fprintd lacks the proprietary Synaptics Metallica Match-in-Sensor driver.
# We mask stock fprintd so open-fprintd can cleanly provide the standard D-Bus API.
systemctl stop fprintd.service 2>/dev/null || true
systemctl mask fprintd.service 2>/dev/null || true

echo "[3/7] Installing driver core to /usr/local/lib/hp-fingerprint-mouse/..."
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

echo "[4/7] Deploying sensor firmware to system runtime directories..."
mkdir -p /var/lib/python-validity/firmware/
mkdir -p /usr/share/python-validity/firmware/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /var/lib/python-validity/firmware/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /usr/share/python-validity/
cp "${SCRIPT_DIR}/firmware/6_07f_hp_mis_qm.xpfwext" /usr/share/python-validity/firmware/
chmod 644 /var/lib/python-validity/firmware/6_07f_hp_mis_qm.xpfwext
chmod 644 /usr/share/python-validity/6_07f_hp_mis_qm.xpfwext

echo "[5/7] Installing D-Bus bus policy configurations..."
cp "${SCRIPT_DIR}/net.reactivated.Fprint.conf" /etc/dbus-1/system.d/
cp "${SCRIPT_DIR}/io.github.uunicorn.Fprint.conf" /etc/dbus-1/system.d/
systemctl reload dbus 2>/dev/null || true

echo "[6/7] Installing udev permissions rules..."
cp "${SCRIPT_DIR}/70-hp-fingerprint-mouse.rules" /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger --attr-match=idVendor=06cb --attr-match=idProduct=00c3 || udevadm trigger

echo "[7/7] Installing and starting systemd services..."
cp "${SCRIPT_DIR}/open-fprintd.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/python3-validity.service" /etc/systemd/system/

systemctl daemon-reload
if [ -r /sys/class/dmi/id/product_serial ]; then
    cat /sys/class/dmi/id/product_serial > /etc/hp-fingerprint-mouse-serial.txt 2>/dev/null || true
    chmod 644 /etc/hp-fingerprint-mouse-serial.txt 2>/dev/null || true
fi
rm -f /var/run/python-validity/backoff 2>/dev/null || true
systemctl reset-failed python3-validity.service 2>/dev/null || true
systemctl enable open-fprintd.service
systemctl enable python3-validity.service

systemctl restart open-fprintd.service
systemctl restart python3-validity.service

# Configure PAM for fingerprint auth
echo "[*] Ensuring PAM fingerprint authentication is enabled..."
if command -v pam-auth-update >/dev/null 2>&1; then
    pam-auth-update --enable fprintd || true
fi

sleep 2

echo ""
echo "===================================================================="
echo " Installation Complete!"
echo "===================================================================="
echo "Service Status:"
systemctl status open-fprintd.service --no-pager --lines=3 || true
echo "---"
systemctl status python3-validity.service --no-pager --lines=3 || true

echo ""
echo "Next Steps to Enroll and Use Your Fingerprint:"
echo "1. Run the enrollment command:"
echo "   fprintd-enroll"
echo "   (Touch the sensor on your HP mouse repeatedly when prompted)"
echo ""
echo "2. Verify your enrolled print:"
echo "   fprintd-verify"
echo ""
echo "3. Use your fingerprint for sudo, lock screen, and system login!"
echo "===================================================================="
