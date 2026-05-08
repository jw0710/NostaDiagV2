# Changelog

---

## V2.0

Complete rewrite with a new web-based UI (pywebview + HTML/CSS/JS).

**New**
- Fully redesigned interface — dark theme, customizable accent color and font
- NASA-style boot animation during startup
- Persistent settings (theme, font, accent) stored in AppData
- First-launch welcome guide with interactive walkthrough
- Undervolting tab — CELL and RSX voltage presets + manual slider
- Voltage ranges reference image built-in
- Fan editor rewritten with CELL + RSX tables (10 phases each) + thermal shutdown
- EEPROM memory inspector
- Checksum gate toggle
- Direct command input panel
- Credits tab
- Connection guide with testpad images per PS3 model
- Sidebar navigation with keyboard shortcuts (F1-F12)
- Sandbox mode indicator in top bar
- Windows installer (Inno Setup)
- Settings auto-reset if startup hangs for more than 2 minutes

**Changed**
- Switched from tkinter to pywebview (no more grey Windows widgets)
- Settings now stored in `%APPDATA%\NostaDiag\` instead of next to the .exe
- Version badge updated to V2.0

---

## v1.00

Initial release.

- Basic Syscon UART communication
- RSX autopatch (40nm / 65nm)
- CXR to CXRF conversion
- Checksum correction
- Fan table editor
- Quick diagnostic commands
- Built-in Sysko helper
- Standalone .exe via PyInstaller
