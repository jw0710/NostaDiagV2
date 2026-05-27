# Changelog

---

## V2.0.1 — 27.05.2026

- **CXR mode gate** — in CXR mode only CXR→CXRF Patch and Direct Commands are accessible; all other workflows are locked with tooltip "Requires CXRF mode"
- **Undervolt slider** — full NCP5318 VRD10 table, all 62 voltage steps (0.8375V–1.6000V, 0.00125V steps); slider was previously limited to a narrow range around the preset
- **Voltage Ranges reference** — moved into the configure step (step 2) as a collapsible section; removed from the done step where it was useless
- **Slider markers** — ★ Preset above slider, ▶ Stock below slider; no overlap even when preset and stock are adjacent
- **Overvolt indicator** — voltage display turns red when selected voltage exceeds stock
- **Ko-fi support link** — added to Credits tab (banner) and sidebar footer
- **Connection guide** — `select_option.png` shown by default on open instead of blank placeholder
- **Terminal auth block** — "This is neither the time nor the place for that!" (Professor Oak)
- **`.gitignore`** — added; excludes build/, dist/, *.spec, *.iss, __pycache__, old V1 file, OS/IDE junk

---

## V2.0

Complete rewrite with a new web-based UI (pywebview + HTML/CSS/JS).

**New**
- Fully redesigned interface — light/dark theme, customizable accent color and font
- Silver/blue light mode as default, dark/green opt-in via Settings
- Startup theme applied instantly via sync preload — no flash on boot
- NASA-style boot animation during startup
- Persistent settings (theme, font, accent) stored in `%APPDATA%\NostaDiag\`
- First-launch welcome guide with interactive walkthrough
- Bridge watchdog — if startup hangs >120s, prompts to reset settings and restart
- Auth gate — all sensitive workflows locked until Syscon authentication succeeds
- CXR mode restriction — only CXR→CXRF patch and Direct Commands available in CXR mode
- Sandbox mode — full simulation, no UART traffic sent
- Undervolting tab — CELL and RSX voltage presets + full manual VID slider
- Complete NCP5318 VRD10 table — all 62 voltage steps (0.8375V–1.6000V, 12.5mV steps)
- Voltage ranges reference by DoublesAdvocat — built into the undervolt configure step
- RSX Autopatch — 28nm, 40nm, 65nm, 90nm variants, Standard and GGB
- RSX Config Backup / Restore — save and re-apply RSX register state to file
- Fan editor rewritten with CELL + RSX tables (10 phases each) + thermal shutdown
- EEPROM memory inspector
- Checksum gate toggle
- Direct command input panel with auth gate and autocomplete
- Connection guide with testpad images per PS3 model — pre-loaded select image on open
- Error codes tab — searchable PS3 developer wiki reference
- Credits tab — contributor cards + Ko-fi support link
- Sidebar navigation with keyboard shortcuts (F1–F12)
- Ko-fi donate button in sidebar footer and credits tab
- Engineering Preview badge in app header
- Windows installer (Inno Setup)

**Changed**
- Switched from tkinter to pywebview (no more grey Windows widgets)
- Settings path moved to `%APPDATA%\NostaDiag\` — no permission issues after install
- Auth step removed from CXR→CXRF and RSX steppers — handled globally now
- Voltage slider now covers full VID table range instead of a narrow preset window
- Stock voltage marker shown below slider, preset marker above — no overlap

---

## v1.00

Initial release.

- Basic Syscon UART communication
- RSX autopatch (40nm / 65nm)
- CXR to CXRF conversion
- Checksum correction
- Fan table editor
- Quick diagnostic commands
- Standalone .exe via PyInstaller
