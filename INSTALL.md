# NostaDiag V2.0 - Installation & Setup Guide

---

## 1. Install NostaDiag

1. Download `NostaDiag_v2.0_Setup.exe` from the [Releases page](../../releases)
2. Run the installer
3. Optional: create a desktop shortcut (checkbox during install)
4. Launch NostaDiag from the Start Menu or desktop

Settings are stored in `%APPDATA%\NostaDiag\settings.json` — no admin rights needed after install.

---

## 2. Hardware Requirements

- PS3 console (FAT, Slim, or Super Slim)
- UART-TTL adapter (3.3V logic level — do NOT use 5V)
- USB cable (adapter to PC)

Recommended adapters:
- CP2102
- CH340
- FT232RL

> Make sure your adapter runs at 3.3V. A 5V adapter can damage the Syscon.

---

## 3. Connect the UART Adapter

The connection points are on the PS3 motherboard (Syscon UART pads).
NostaDiag has a built-in connection guide with images for each PS3 model — open it via the sidebar (Connection Guide).

Basic wiring:

| Adapter | PS3 Syscon pad |
|---------|----------------|
| TX      | RX             |
| RX      | TX             |
| GND     | GND            |

Do not connect the VCC pin of the adapter to the PS3.

---

## 4. Driver Installation

If Windows does not recognize your UART adapter:

- **CP2102**: [Silicon Labs CP210x drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
- **CH340**: [CH340 drivers](https://www.wch-ic.com/downloads/CH341SER_EXE.html)
- **FT232**: [FTDI drivers](https://ftdichip.com/drivers/vcp-drivers/)

After installing the driver, the adapter will appear as a COM port in Device Manager.

---

## 5. First Launch

1. Connect the UART adapter to your PC
2. Launch NostaDiag
3. Select the correct **COM port** from the dropdown (top left)
4. Select the correct **SC Type**:

| SC Type | Use for |
|---------|---------|
| CXR | FAT PS3, older Syscon (COK-001) |
| CXRF | FAT PS3, Mullion Syscon (fan control available) |
| SW | Slim / Super Slim |

5. Click **Auth PS3** to authenticate with the Syscon
6. A welcome guide will appear on first launch — follow it to get started

---

## 6. Sandbox Mode

If you don't have hardware connected, enable **Sandbox** (toggle in the top bar).
All commands will simulate responses — safe for testing the UI.

---

## 7. Uninstall

Use Windows Settings > Apps > NostaDiag > Uninstall.

Your settings file (`%APPDATA%\NostaDiag\settings.json`) is kept by default.
To fully remove it, delete that folder manually after uninstalling.

---

## Troubleshooting

**"Save failed: Permission denied"**
Make sure you are running the installer version (not the portable .exe placed inside Program Files manually).
The installer handles paths correctly.

**COM port not showing up**
Install the driver for your UART adapter (see Section 4).
Try unplugging and re-plugging the adapter, then refresh the port list.

**App takes a long time to start**
NostaDiag uses WebView2 (Microsoft Edge runtime) which may take 10-20 seconds on first cold start.
A startup animation plays while it loads.
If startup takes more than 2 minutes, a dialog will offer to reset settings automatically.

**"Auth failed" or no response from Syscon**
- Check TX/RX wiring (swap them if unsure)
- Verify SC Type matches your console
- Make sure the PS3 is powered on (standby is enough)
- Try a different baud rate adapter if using a clone

---

## Support

- Report bugs: [GitHub Issues](../../issues)
- Instagram: [@NostaMods](https://www.instagram.com/nostamods/)
