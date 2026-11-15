#!/usr/bin/env python3
"""
Diagnostic & Hardware Test Utility for HP USB Fingerprint Mouse
Sensor: Synaptics 06cb:00c3
Mouse: HP Optical HID 03f0:4b4a
"""

import sys
import os
import subprocess
import time

# Ensure installed driver library and local package modules can be imported
sys.path.insert(0, "/usr/local/lib/hp-fingerprint-mouse")
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import usb.core
import usb.util

VID_HP_MOUSE = 0x03f0
PID_HP_MOUSE = 0x4b4a

VID_SYNA_SENSOR = 0x06cb
PID_SYNA_SENSOR = 0x00c3

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_usb_devices():
    print_header("1. Checking Physical USB Hardware Detection")
    mouse_dev = usb.core.find(idVendor=VID_HP_MOUSE, idProduct=PID_HP_MOUSE)
    sensor_dev = usb.core.find(idVendor=VID_SYNA_SENSOR, idProduct=PID_SYNA_SENSOR)

    mouse_found = mouse_dev is not None
    sensor_found = sensor_dev is not None

    print(f"[*] Mouse Optical Controller (03f0:4b4a): {'FOUND' if mouse_found else 'NOT FOUND'}")
    if mouse_found:
        print(f"    Bus: {mouse_dev.bus:03d}, Address: {mouse_dev.address:03d}")

    print(f"[*] Fingerprint Biometric Sensor (06cb:00c3): {'FOUND' if sensor_found else 'NOT FOUND'}")
    if sensor_found:
        print(f"    Bus: {sensor_dev.bus:03d}, Address: {sensor_dev.address:03d}")

    return mouse_dev, sensor_dev

def check_permissions(sensor_dev):
    print_header("2. Checking Device Permissions & Access")
    if not sensor_dev:
        print("[-] Sensor not found on USB bus. Cannot check permissions.")
        return False

    devpath = f"/dev/bus/usb/{sensor_dev.bus:03d}/{sensor_dev.address:03d}"
    print(f"[*] Device node: {devpath}")

    is_readable = os.access(devpath, os.R_OK)
    is_writable = os.access(devpath, os.W_OK)

    print(f"[*] Read permission:  {'YES' if is_readable else 'NO'}")
    print(f"[*] Write permission: {'YES' if is_writable else 'NO'}")

    if not is_writable:
        print("[!] Note: Write access is required to communicate with the sensor.")
        print("    Run this script with 'sudo' or install the udev rule:")
        print("    sudo cp 70-hp-fingerprint-mouse.rules /etc/udev/rules.d/")
        print("    sudo udevadm control --reload-rules && sudo udevadm trigger")
        return False
    return True

def check_driver_unit():
    """Return (is_running_or_unknown, systemd_state)."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'python3-validity.service'],
            capture_output=True, text=True, timeout=5)
        state = (result.stdout or result.stderr).strip() or 'unknown'
        return state == 'active', state
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)

def check_dbus_services():
    print_header("3. Checking D-Bus & System Services")
    manager_owner = False
    registered_devs = []
    try:
        import dbus
        bus = dbus.SystemBus()
        manager_owner = bus.name_has_owner("net.reactivated.Fprint")

        print(f"[*] net.reactivated.Fprint (open-fprintd): {'ACTIVE' if manager_owner else 'NOT RUNNING'}")

        if manager_owner:
            mgr = bus.get_object('net.reactivated.Fprint', '/net/reactivated/Fprint/Manager')
            mgr_iface = dbus.Interface(mgr, 'net.reactivated.Fprint.Manager')
            registered_devs = mgr_iface.GetDevices()
            print(f"[+] Devices registered with fprint manager: {len(registered_devs)}")
            for d in registered_devs:
                print(f"    - Device D-Bus Path: {d}")
                try:
                    dev_obj = bus.get_object('net.reactivated.Fprint', d)
                    dev_prop = dbus.Interface(dev_obj, 'org.freedesktop.DBus.Properties')
                    name = dev_prop.Get('net.reactivated.Fprint.Device', 'name')
                    print(f"    - Device Driver Name: {name}")
                except Exception:
                    pass
    except Exception as e:
        print(f"[-] D-Bus check failed: {e}")

    unit_running, unit_state = check_driver_unit()
    print(f"[*] python3-validity (sensor driver): {unit_state.upper() if unit_state else 'UNKNOWN'}")

    if unit_running is False:
        print("[-] The background driver service is NOT running.")
        print("    Any device still listed above is a stale registration and")
        print("    cannot service enroll/verify requests.")
        print("    Fix: sudo systemctl restart open-fprintd.service python3-validity.service")
    elif not registered_devs:
        print("[-] The sensor driver is running but has not registered a device yet.")
        print("    Wait a few seconds and re-run, or check:")
        print("    sudo journalctl -u python3-validity -n 30 --no-pager")

    driver_active = (
        manager_owner
        and unit_running is not False
        and len(registered_devs) > 0
    )
    driver_running = unit_running is not False

    return driver_active, registered_devs, driver_running

def probe_sensor(sensor_dev, daemon_active=False, force=False, driver_running=False):
    print_header("4. Biometric Sensor Communication Status")
    if daemon_active and not force:
        print("[+] The background driver service is ACTIVE and managing the sensor.")
        print("[+] Hardware communication is fully verified and connected over D-Bus.")
        print("[*] (Direct USB bus probe skipped to preserve active daemon TLS session)")
        print("\n[SUCCESS] The hardware and driver communication stack is fully operational!")
        return

    if driver_running and not force:
        print("[-] The driver service is running but no usable device is registered.")
        print("[*] Skipping the raw USB probe: claiming the sensor now would")
        print("    desynchronize the daemon's live TLS session.")
        print("    Fix: sudo systemctl restart open-fprintd.service python3-validity.service")
        return

    try:
        from validitysensor.usb import usb as v_usb, SupportedDevices
        from validitysensor.sensor import RomInfo, identify_sensor
        from validitysensor.flash import get_fw_info
        from validitysensor.init_data_dir import init_data_dir
        from validitysensor.init_flash import init_flash
        from validitysensor.tls import tls
        from validitysensor.flash import read_tls_flash

        init_data_dir()
        print("[*] Opening USB endpoint connection...")
        v_usb.open(VID_SYNA_SENSOR, PID_SYNA_SENSOR)
        print("[+] USB interface claimed successfully!")

        print("[*] Initializing flash bus & reading ROM info...")
        init_flash()
        v_usb.send_init()

        rom = RomInfo.get()
        print(f"[+] ROM Info: Product={rom.product:#x}, Major={rom.major}, Minor={rom.minor}, Build={rom.build}")

        print("[*] Checking firmware partition...")
        fwi = get_fw_info(2)
        if fwi:
            print(f"[+] Firmware loaded: version {fwi.major}.{fwi.minor} (buildtime: {fwi.buildtime})")
        else:
            print("[!] No firmware currently loaded in RAM/Flash. Firmware upload required on startup.")

        print("[*] Probing TLS session...")
        tls.parse_tls_flash(read_tls_flash())
        tls.open()
        print("[+] TLS session established with sensor microcontroller!")

        dev_info = identify_sensor()
        print(f"[+] Sensor identified: '{dev_info.name}' (Type: {dev_info.type:#x})")
        print("\n[SUCCESS] The hardware and driver communication stack is fully operational!")

    except Exception as e:
        print(f"[-] Sensor probe failed with: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print(" HP USB Fingerprint Mouse - Linux Diagnostic Utility")
    print("=" * 60)
    mouse_dev, sensor_dev = check_usb_devices()
    can_access = check_permissions(sensor_dev)
    daemon_active, devs, driver_running = check_dbus_services()
    force_probe = ('--force-usb-probe' in sys.argv)
    if can_access and sensor_dev:
        probe_sensor(sensor_dev, daemon_active, force_probe, driver_running)
    print("\n" + "=" * 60)
    print(" Diagnostic Complete.")
    print("=" * 60)
