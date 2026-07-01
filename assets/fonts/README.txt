Self-hosted UI fonts for NostaDiag
==================================

These fonts are bundled locally so the app has no CDN / network dependency
at startup (see the @font-face rules in webui/index.html).

Files (latin subset, woff2):
  Inter-400.woff2 / -500 / -600 / -700          UI font  (var --ui)
  JetBrainsMono-400.woff2 / -500 / -600         mono font (var --mono)

Both fonts are licensed under the SIL Open Font License, Version 1.1.
The full license and copyright notices are in:
  Inter-OFL.txt
  JetBrainsMono-OFL.txt

Sources:
  Inter          https://github.com/rsms/inter
  JetBrains Mono https://github.com/JetBrains/JetBrainsMono

If you add more weights/styles later, drop the woff2 here and add a matching
@font-face rule in webui/index.html.
