# Contributing to NostaDiag

Thanks for your interest in improving NostaDiag! This is a repair/diagnostic
tool for PS3 Syscon work — correctness matters because wrong writes can damage
hardware. Please keep that in mind.

## Running from source

```bash
pip install -r requirements.txt
python app_web.py
```

No build step is needed for development — `app_web.py` starts a local server and
opens the pywebview window. Use **Sandbox Mode** (top bar) to exercise the whole
UI without any hardware connected.

## Project layout

```
app_web.py            Python backend + local HTTP server + pywebview bridge
ps3_uart.py           UART / Syscon protocol layer (CXR / CXRF / SW)
webui/index.html      Entire frontend (HTML + CSS + JS, single file)
assets/               Icons, fonts, connection-guide images, error reference
sandbox_data.json     Canned responses for Sandbox Mode
syscon_config.json    Syscon command/config data
build.bat             Build the standalone .exe (PyInstaller, windowed)
build_debug.bat       Debug build (console visible + no UPX) for diagnostics
NostaDiag.spec        Generated PyInstaller spec
NostaDiag_Setup.iss   Inno Setup installer script
```

## Guidelines

- **Test in Sandbox Mode first.** Any command-format change must be verified
  against the sandbox mock and, for hardware writes, against a real console.
- **Match the existing style.** The frontend is a single self-contained file;
  keep new CSS/JS in the same idiom.
- **Don't break offline use.** Fonts are self-hosted in `assets/fonts/`; do not
  reintroduce CDN dependencies at startup.
- **Update the [CHANGELOG](CHANGELOG.md)** for user-visible changes.

## Reporting bugs

Open an issue with: PS3 model + SC type, what you did, what you expected, and the
terminal output. For a startup/crash issue, build with `build_debug.bat` and run
`dist\NostaDiag_debug.exe` from a terminal so the traceback is visible.

## License

By contributing you agree your work is released under the
[NostaDiag License v1.0](LICENSE.txt).
