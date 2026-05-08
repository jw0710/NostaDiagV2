# NostaDiag V2.0

> A modern diagnostic and repair tool for PS3 Syscon operations — built by NostaMods.

[![License](https://img.shields.io/badge/license-NostaDiag%20v2.0-blue.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-2.0-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()

![NostaDiag V2.0](gh_assets/main.png)

---

## What is NostaDiag?

NostaDiag is a standalone Windows tool for working with PS3 Syscon hardware via UART serial connection.
It provides a clean interface for diagnostics, patching, fan management, and undervolting — no Python installation required.

---

## Features

**Diagnostics**
- Health check (BSN, version, board config, temps, error log)
- Error log read & clear
- Temperature sensor readout
- Boot error count, RTC

**Patching**
- RSX autopatch (40nm / 65nm, Standard / GGB)
- CXR to CXRF conversion
- Checksum correction (auto-detect + apply)
- Checksum gate toggle
- EEPROM memory inspector (read/write)

**Fan Management**
- CELL + RSX fan table editor (10 phases each)
- Thermal shutdown temperature
- Preset profiles: Stock, Quiet, Performance
- Fan curve visualization

**Undervolting**
- CELL and RSX voltage presets by nm node
- Manual voltage slider (VID table, 0.8375V - 1.6000V)
- Voltage ranges reference image built-in

**Tools**
- Direct UART command input
- Sandbox mode (test without real hardware)
- Persistent settings (theme, font, accent color)
- Built-in connection guide with testpad images
- PS3 Developer Wiki error code reference

---

## Screenshots

| Startup | Fan Tuning |
|---------|------------|
| ![Startup](Screenshots/StartUp_Screen.PNG) | ![Fan Tuning](Screenshots/FanTuning.PNG) |

| RSX Autopatch | Undervolting |
|---------------|--------------|
| ![RSX](Screenshots/RSX_Autopatch.PNG) | ![UV](Screenshots/Undervolting1.PNG) |

| Connection Guide | Settings |
|-----------------|----------|
| ![Guide](Screenshots/connection_guide.PNG) | ![Settings](Screenshots/settings.PNG) |

---

## Requirements

- Windows 10 or Windows 11
- UART-TTL adapter connected to PS3 Syscon
- No Python installation required (standalone .exe)

---

## Installation

Download `NostaDiag_v2.0_Setup.exe` from [Releases](../../releases) and run it.

See [INSTALL.md](INSTALL.md) for detailed setup instructions including hardware wiring.

---

## SC Type - Which one do I pick?

| SC Type | Console | Fan Control |
|---------|---------|-------------|
| CXR | FAT (older Syscon, COK-001) | No |
| CXRF | FAT (Mullion Syscon) | Yes |
| SW | Slim / Super Slim | No |

---

## Credits

- **M4j0r** — reverse engineering, VID voltage table research
- **Sage** — testing and community support
- **DoublesAdvocat** — hardware research contributions
- **Calyps0man** — documentation and community contributions
- PSX-Place community — Frankenstein mod documentation

---

## License

[NostaDiag License v1.0](LICENSE.txt) — personal, educational and repair use.
Commercial use requires visible credit. Do not rebrand or remove credits.

---

## Links

- Instagram: [@NostaMods](https://www.instagram.com/nostamods/)
- Issues: [GitHub Issues](../../issues)

> Use your brain before your click.
