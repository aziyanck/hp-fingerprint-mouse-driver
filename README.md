# HP USB Fingerprint Mouse — Linux Driver & Support

Native Linux biometric driver, firmware loader, systemd daemons, and PAM integration for the **HP USB Fingerprint Mouse**.

Supports **Ubuntu / Debian** (via turnkey `.deb` or script) and **Arch Linux** (via script or `PKGBUILD`).

---

## Hardware Overview

Inside a single USB cable, this mouse contains two independent hardware devices connected via an internal USB 2.0 hub:

| Component | USB Hardware ID | Subsystem & Driver |
| :--- | :--- | :--- |
| **Optical Mouse** | `03f0:4b4a` | Standard Linux HID kernel module (`usbhid` / `evdev`) |
| **Biometric Sensor** | `06cb:00c3` | Synaptics Metallica Match-in-Sensor (MIS) capacitive touch sensor |

---

## Features

* **Full Match-in-Sensor Support:** Uses authentic Synaptics microcode (`6_07f_hp_mis_qm.xpfwext`) for autonomous template matching.
* **Auto-Reconnecting Hotplug Daemon:** Automatic recovery when the mouse is unplugged and replugged via udev and systemd.
* **Standard D-Bus Interface:** Seamlessly bridges to `open-fprintd` (`net.reactivated.Fprint`), integrating with standard `fprintd` client tools.
* **System Authentication:** Works for `sudo`, GDM / SDDM login, Polkit prompts, and lock screen unlock.
* **Diagnostic Utility:** Includes `hp-mouse-test` to inspect hardware status and D-Bus communications without disrupting active sessions.

---

## Installation

### For Ubuntu / Debian-based Systems

#### Method 1: Pre-built Debian Package (Recommended)
```bash
cd hp-fingerprint-mouse-linux
sudo dpkg -i hp-fingerprint-mouse-support_1.0-1_all.deb
sudo apt-get install -f   # Resolves any missing dependencies automatically
```

#### Method 2: Automated Installation Script
```bash
cd hp-fingerprint-mouse-linux
sudo ./install.sh
```

---

### For Arch Linux

#### Method 1: Automated Arch Installer (Recommended)
```bash
cd hp-fingerprint-mouse-linux
sudo ./install-arch.sh
```
*(Automatically installs dependencies using `pacman`, copies driver files, sets up udev/D-Bus, and starts services).*

#### Method 2: Native Arch Package (`PKGBUILD`)
```bash
cd hp-fingerprint-mouse-linux/arch
makepkg -si
```

---

## Enrollment & Usage

### 1. Diagnostic Check
Verify that the device and services are healthy:
```bash
hp-mouse-test
```
You should see:
```text
[+] The background driver service is ACTIVE and managing the sensor.
[SUCCESS] The hardware and driver communication stack is fully operational!
```

### 2. Enroll Your Fingerprint
Run the enrollment utility:
```bash
fprintd-enroll
```
*Touch the sensor on your mouse repeatedly (around 5 to 10 touches) until enrollment reaches 100%.*

To enroll a specific finger:
```bash
fprintd-enroll -f right-index-finger
```

### 3. Verify Enrollment
```bash
fprintd-verify
```
*Touch the sensor. You should see `Verify result: verify-match (done)`.*

### 4. Enable Fingerprint Authentication for `sudo` and Login

#### On Ubuntu / Debian:
```bash
sudo pam-auth-update
```
*(Ensure `[*] Fingerprint authentication` is checked with the spacebar, then press Tab and Enter to Save).*

#### On Arch Linux:
1. **For `sudo`:** Add `auth sufficient pam_fprintd.so` as the first auth rule in `/etc/pam.d/sudo`:
   ```pam
   #%PAM-1.0
   auth      sufficient pam_fprintd.so
   auth      include    system-auth
   ...
   ```
2. **For Login / Lock Screen:** Add `auth sufficient pam_fprintd.so` at the top of the auth section in `/etc/pam.d/system-local-login`.

---

## Uninstallation

To remove the driver and restore default settings:

### Ubuntu / Debian:
```bash
sudo dpkg -P hp-fingerprint-mouse-support
```
*Or run:*
```bash
sudo ./uninstall.sh
```

### Arch Linux:
```bash
sudo pacman -R hp-fingerprint-mouse-support
```
*Or run:*
```bash
sudo ./uninstall.sh
```

---

## Project Structure

```text
hp-fingerprint-mouse-linux/
├── 70-hp-fingerprint-mouse.rules    # Udev hotplug & permissions rules
├── arch/
│   └── PKGBUILD                     # Arch Linux package build script
├── firmware/
│   └── 6_07f_hp_mis_qm.xpfwext      # Authenticated Synaptics microcode
├── hp-fingerprint-mouse-support_*.deb # Turnkey Debian package
├── install.sh                       # Ubuntu/Debian installer script
├── install-arch.sh                  # Arch Linux installer script
├── openfprintd/                     # FreeDesktop D-Bus bridge implementation
├── python-validity-dbus/            # Sensor daemon service entrypoint
├── test_hp_mouse.py                 # Diagnostic test utility (installed as hp-mouse-test)
├── tests/                           # Automated pytest regression test suite (61 tests)
├── uninstall.sh                     # Uninstallation script
└── validitysensor/                  # Low-level USB, flash, and TLS driver engine
```

---

## License

Driver engine and utilities are distributed under the GNU General Public License v3.0.
Microcode firmware (`6_07f_hp_mis_qm.xpfwext`) is copyright Synaptics / HP.
