import os
import sys
import json
import threading
import re

# ── Suppress noisy WebView2 / accessibility recursion warnings on Windows ────
# Known pywebview bug: Windows UI-Automation probes the WebView's
# AccessibilityObject.Bounds, which can return chained .Empty.Empty.Empty…
# objects whose repr() blows the recursion stack. Doesn't affect functionality
# — just spams stderr. Filter those lines and bump the recursion limit.
sys.setrecursionlimit(10000)

class _StderrFilter:
    def __init__(self, real):
        self.real = real
    def write(self, s):
        if not s:
            return
        if 'Empty.Empty.Empty' in s or 'AccessibilityObject' in s or 'maximum recursion depth' in s:
            return
        self.real.write(s)
    def flush(self):
        try: self.real.flush()
        except Exception: pass
    def __getattr__(self, name):
        return getattr(self.real, name)

sys.stderr = _StderrFilter(sys.stderr)

import webview

from ps3_uart import PS3UART, _ps3_annotate


def resource_path(rel_path):
    """Get absolute path to a bundled resource — works in dev and as PyInstaller .exe."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


class Api:
    def __init__(self):
        self.window = None
        self.sandbox = False
        self.console_running = False

    # ── internal helpers ──────────────────────────────────────────────────────

    def _log(self, text, type_='dim'):
        if not self.window:
            return
        try:
            self.window.evaluate_js(
                'appendLog({},{})'.format(json.dumps(str(text)), json.dumps(type_))
            )
        except Exception as e:
            # JS context not ready yet, or pywebview queue issue — ignore silently
            print('[log-fallback] {}: {}'.format(type_, text))

    def _js(self, expr):
        if not self.window:
            return
        try:
            self.window.evaluate_js(expr)
        except Exception as e:
            print('[js-fallback skipped]: {}'.format(str(e)[:80]))

    def _ps3(self, port, sc_type):
        if self.sandbox:
            return PS3UART("SANDBOX", sc_type or "CXR", "57600", sandbox_mode=True)
        if not port or not sc_type:
            raise ValueError("Port and SC type must be selected")
        speed = "115200" if sc_type == "CXRF" else "57600"
        return PS3UART(port, sc_type, speed, sandbox_mode=False)

    def _thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── public API (called from JS) ───────────────────────────────────────────

    def get_ports(self):
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def open_external(self, what):
        """Open a bundled file or URL in the default system browser/handler."""
        import webbrowser
        path_map = {
            'errors_wiki':   resource_path(os.path.join('assets', 'Errors', 'Error Codes - PS3 Developer wiki.html')),
        }
        target = path_map.get(what, what)
        try:
            if os.path.exists(target):
                webbrowser.open('file:///' + target.replace('\\', '/'))
            else:
                webbrowser.open(target)
            return {'ok': True}
        except Exception as e:
            self._log('Could not open {}: {}'.format(target, e), 'err')
            return {'ok': False}

    def set_sandbox(self, enabled):
        self.sandbox = bool(enabled)
        self._log('Sandbox mode {}'.format('ENABLED' if enabled else 'disabled'),
                  'warn' if enabled else 'dim')
        return {'ok': True}

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self, port, sc_type):
        def _run():
            try:
                self._log('> auth ({})'.format(sc_type), 'cmd')
                ps3 = self._ps3(port, sc_type)
                result = ps3.auth()
                ok = 'successful' in result.lower()
                self._log(result, 'ok' if ok else 'err')
                if ok:
                    self._js('onAuthOK()')
                else:
                    self._js('onAuthFail({})'.format(json.dumps(result)))
            except Exception as e:
                self._log('Auth error: {}'.format(e), 'err')
                self._js('onAuthFail({})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    # ── Generic command ───────────────────────────────────────────────────────

    def send_command(self, port, sc_type, cmd):
        def _run():
            try:
                self._log('> ' + cmd, 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=1)
                out = ps3.fmt(ret)
                t = 'err' if ret[0] == 0xFFFFFFFF else 'ok'
                for line in out.splitlines():
                    self._log(line, t)
                    ann = _ps3_annotate(line)
                    if ann:
                        self._log(ann, 'warn')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Quick diagnostic commands ─────────────────────────────────────────────

    def quick_cmd(self, port, sc_type, cmd_name):
        CMD_MAP = {
            'errlog':    ('errlog',      1.0),
            'checksum':  ('csum',        1.0),
            'eepcsum':   ('eepcsum',     1.0),
            'clearerrlog': ('clearerrlog', 0.5),
            'tsensor':   ('tsensor',     0.5),
            'becount':   ('becount',     0.5),
            'getrtc':    ('getrtc',      0.5),
        }
        if cmd_name == 'auth':
            return self.authenticate(port, sc_type)
        entry = CMD_MAP.get(cmd_name)
        if not entry:
            self._log('Unknown quick command: ' + cmd_name, 'err')
            return {'ok': False}

        def _run():
            try:
                cmd, wait = entry
                self._log('> ' + cmd, 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=wait)
                out = ps3.fmt(ret)
                t = 'err' if ret[0] == 0xFFFFFFFF else 'ok'
                for line in out.splitlines():
                    self._log(line, t)
                    ann = _ps3_annotate(line)
                    if ann:
                        self._log(ann, 'warn')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Power ─────────────────────────────────────────────────────────────────

    def power_toggle(self, port, sc_type, currently_running):
        def _run():
            try:
                cmd = 'shutdown' if currently_running else 'bringup'
                self._log('> ' + cmd, 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=1)
                out = ps3.fmt(ret)
                ok = ret[0] != 0xFFFFFFFF
                self._log(out, 'ok' if ok else 'err')
                new_state = (not currently_running) if ok else currently_running
                self.console_running = new_state
                self._js('onPowerChange({})'.format('true' if new_state else 'false'))
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Health Check ──────────────────────────────────────────────────────────

    def health_check(self, port, sc_type):
        CHECKS = [
            ('bsn',          'bsn',          0.5),
            ('version',      'version',      0.5),
            ('boardconfig',  'boardconfig',  0.7),
            ('temperatures', 'tsensor',      0.5),
            ('becount',      'becount',      0.5),
            ('patchver',     'patchvereep',  0.5),
            ('errlog',       'errlog',       1.0),
        ]

        def _run():
            try:
                ps3 = self._ps3(port, sc_type)
                data = {}
                for key, cmd, wait in CHECKS:
                    self._log('Health: reading {}…'.format(key), 'dim')
                    try:
                        ret = ps3.command(cmd, wait=wait)
                        data[key] = ps3.fmt(ret)
                    except Exception as e:
                        data[key] = 'Error: {}'.format(e)
                self._js('onHealthData({})'.format(json.dumps(data)))
                self._log('Health check complete', 'ok')
            except Exception as e:
                self._log('Health check error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── RSX Autopatch ─────────────────────────────────────────────────────────

    # ── Internal helpers for patch execution ─────────────────────────────────

    def _execute_patch_cmds(self, ps3, cmds):
        """Execute a list of write commands in order, verify each step.
        Returns (ok: bool, fail_msg: str)."""
        import time as _time
        for i, cmd in enumerate(cmds, 1):
            self._log('[{}/{}] {}'.format(i, len(cmds), cmd), 'cmd')
            ret = ps3.command(cmd, wait=1)
            out = ps3.fmt(ret)
            ok = ret[0] != 0xFFFFFFFF
            self._log(out, 'ok' if ok else 'err')
            if not ok:
                msg = 'Failed at step {}: {}'.format(i, out)
                self._log(msg, 'err')
                return False, msg
            _time.sleep(0.3)
        return True, ''

    def _parse_bytes_from_response(self, ret, length):
        """Parse raw byte values out of a PS3UART command response.
        Reuses the same tokenisation logic as read_memory()."""
        tokens = []
        for item in ret[1]:
            for piece in str(item).replace('\r', ' ').replace('\n', ' ').split():
                tokens.append(piece)
        hexset = set('0123456789abcdefABCDEF')
        bytes_list = []
        for tok in tokens:
            t = tok.strip()
            if len(t) == 2 and all(c in hexset for c in t):
                bytes_list.append(int(t, 16))
            elif len(t) == 4 and all(c in hexset for c in t):
                bytes_list.append(int(t[0:2], 16))
                bytes_list.append(int(t[2:4], 16))
        return bytes_list[:length]

    # ── RSX Autopatch ─────────────────────────────────────────────────────────

    def patch_rsx(self, port, sc_type, nm, model='standard'):
        PATCHES = {
            '40nm_standard': [
                "w 3242 03 61 82 80 01 91",
                "w 3254 21 EC",
                "w 348B 8B",
                "w 34AF 8B",
            ],
            '40nm_ggb': [
                "w 3242 03 61 82 80 01 91",
                "w 3254 21 EB",
                "w 348B 8B",
                "w 34AF 8B",
            ],
            '65nm_standard': [
                "w 3242 03 A2 03 B0 07 71",
                "w 3254 21 E8",
                "w 348B 88",
                "w 34AF 88",
            ],
            # Source: psdevwiki.com/ps3/Talk:Rambus_Registers
            # 28nm Training Data identical to 40nm (REX-001 board, PSX-Place forum)
            '28nm_standard': [
                "w 3242 03 61 82 80 01 91",
                "w 3254 21 EE",
                "w 348B 8B",
                "w 34AF 8B",
            ],
            # Source: psdevwiki.com/ps3/Talk:Rambus_Registers (COK-001 / COK-002)
            # Mirror bytes 0x348B / 0x34AF are UNVERIFIED — experimental
            '90nm_standard': [
                "w 3242 09 70 89 70 06 90",
                "w 3254 21 E4",
                "w 348B 90",
                "w 34AF 90",
            ],
        }
        key = '{}_{}'.format(nm, model)
        cmds = PATCHES.get(key)
        if not cmds:
            self._log('Unknown patch combination: {}/{}'.format(nm, model), 'err')
            return {'ok': False}

        def _run():
            try:
                if sc_type != 'CXRF':
                    self._log('RSX Patch requires CXRF mode!', 'err')
                    self._js('onPatchDone(false,"CXRF mode required for RSX patch")')
                    return
                label = 'RSX {}NM Patch ({})'.format(nm.upper().replace('NM', 'nm'), model.upper())
                self._log('=== {} ==='.format(label), 'cmd')
                ps3 = self._ps3(port, sc_type)
                ok, fail_msg = self._execute_patch_cmds(ps3, cmds)
                if ok:
                    self._log('{} completed!'.format(label), 'ok')
                    self._js('onPatchDone(true,{})'.format(json.dumps(label + ' completed successfully')))
                else:
                    self._js('onPatchDone(false,{})'.format(json.dumps(fail_msg)))
            except Exception as e:
                self._log('Patch error: {}'.format(e), 'err')
                self._js('onPatchDone(false,{})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    # ── RSX Config Backup / Restore ───────────────────────────────────────────

    @staticmethod
    def _resolve_dialog_path(result):
        """Normalise the return value of create_file_dialog across pywebview versions.
        May return: str, tuple/list of str, tuple/list with None, or None.
        Returns a valid path string, or None if the dialog was cancelled."""
        if result is None:
            return None
        if isinstance(result, (list, tuple)):
            path = result[0] if result else None
        else:
            path = result  # already a str
        return path if path else None

    def rsx_backup(self, port, sc_type):
        def _run():
            try:
                import datetime
                self._log('=== RSX Config Backup ===', 'cmd')
                ps3 = self._ps3(port, sc_type)

                # Read board serial
                self._log('Reading board serial...', 'dim')
                serial = 'UNKNOWN'
                try:
                    ret = ps3.command('bsn', wait=0.5)
                    if ret[0] != 0xFFFFFFFF:
                        out = ps3.fmt(ret)
                        hexset = set('0123456789abcdefABCDEF')
                        for tok in reversed(out.split()):
                            t = tok.strip()
                            if len(t) >= 8 and all(c in hexset for c in t):
                                serial = t.upper()
                                break
                except Exception:
                    pass
                self._log('Serial: {}'.format(serial), 'dim')

                # RSX config addresses to back up
                RSX_READS = [
                    ('3242', 6),
                    ('3254', 2),
                    ('348B', 1),
                    ('34AF', 1),
                ]
                rsx_config = {}
                for addr_str, length in RSX_READS:
                    addr = int(addr_str, 16)
                    if sc_type == 'CXRF':
                        cmd = 'r {:04X} {:02X}'.format(addr, length)
                    else:
                        cmd = 'EEP GET {:04X} {:02X}'.format(addr, length)
                    self._log('Reading 0x{}...'.format(addr_str), 'dim')
                    ret = ps3.command(cmd, wait=1)
                    if ret[0] == 0xFFFFFFFF:
                        msg = 'Read failed at 0x{}'.format(addr_str)
                        self._log(msg, 'err')
                        self._js('onBackupDone(false, {})'.format(json.dumps(msg)))
                        return
                    parsed = self._parse_bytes_from_response(ret, length)
                    rsx_config[addr_str] = ' '.join('{:02X}'.format(b) for b in parsed)
                    self._log('  0x{}: {}'.format(addr_str, rsx_config[addr_str]), 'ok')

                now = datetime.datetime.now()
                data = {
                    'serial':     serial,
                    'sc_type':    sc_type,
                    'date':       now.strftime('%Y-%m-%d %H:%M:%S'),
                    'tool':       'NostaDiag',
                    'rsx_config': rsx_config,
                }
                fname = 'RSX_Backup_{}_{}.json'.format(serial, now.strftime('%Y-%m-%d_%H-%M'))

                result = self.window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=fname,
                    file_types=('JSON Files (*.json)',)
                )
                path = self._resolve_dialog_path(result)
                if not path:
                    self._log('Backup cancelled.', 'dim')
                    return
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
                self._log('Backup saved: {}'.format(path), 'ok')
                self._js('onBackupDone(true, {})'.format(json.dumps(os.path.basename(path))))
            except Exception as e:
                self._log('Backup error: {}'.format(e), 'err')
                self._js('onBackupDone(false, {})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    def rsx_restore(self, port, sc_type):
        def _run():
            try:
                result = self.window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    file_types=('JSON Files (*.json)',)
                )
                path = self._resolve_dialog_path(result)
                if not path:
                    return
                with open(path, 'r') as f:
                    data = json.load(f)

                required_addrs = {'3242', '3254', '348B', '34AF'}
                if 'rsx_config' not in data or not required_addrs.issubset(data['rsx_config'].keys()):
                    msg = 'Invalid backup file: missing required RSX config fields'
                    self._log(msg, 'err')
                    self._js('onBackupDone(false, {})'.format(json.dumps(msg)))
                    return

                self._log('Backup loaded: Serial={}, Date={}'.format(
                    data.get('serial', '?'), data.get('date', '?')
                ), 'dim')
                self._js('onRestorePreview({})'.format(json.dumps(data)))
            except Exception as e:
                self._log('Restore error: {}'.format(e), 'err')
                self._js('onBackupDone(false, {})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    def rsx_restore_apply(self, port, sc_type, backup_data):
        def _run():
            try:
                if sc_type != 'CXRF':
                    self._log('RSX Restore requires CXRF mode!', 'err')
                    self._js('onRestoreDone(false, "CXRF mode required for RSX restore")')
                    return
                cfg = backup_data.get('rsx_config', {})
                cmds = [
                    'w 3242 {}'.format(cfg.get('3242', '')),
                    'w 3254 {}'.format(cfg.get('3254', '')),
                    'w 348B {}'.format(cfg.get('348B', '')),
                    'w 34AF {}'.format(cfg.get('34AF', '')),
                ]
                self._log('=== RSX Config Restore ===', 'cmd')
                self._log('Source: Serial={}, Date={}'.format(
                    backup_data.get('serial', '?'), backup_data.get('date', '?')
                ), 'dim')
                ps3 = self._ps3(port, sc_type)
                ok, fail_msg = self._execute_patch_cmds(ps3, cmds)
                if ok:
                    self._log('RSX config restored successfully.', 'ok')
                    self._log('Run Checksum Correction after restore!', 'warn')
                    self._js('onRestoreDone(true, "RSX config restored. Run Checksum Correction!")')
                else:
                    self._js('onRestoreDone(false, {})'.format(json.dumps(fail_msg)))
            except Exception as e:
                self._log('Restore error: {}'.format(e), 'err')
                self._js('onRestoreDone(false, {})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    # ── CXR -> CXRF ───────────────────────────────────────────────────────────

    def cxr_to_cxrf(self, port, sc_type):
        def _run():
            try:
                self._log('=== CXR -> CXRF Patcher ===', 'cmd')
                ps3 = self._ps3(port, sc_type)

                self._log('Step 1: Reading EEP GET 3961 01…', 'dim')
                ret = ps3.command('EEP GET 3961 01', wait=1)
                if ret[0] == 0xFFFFFFFF:
                    self._log('Read failed: {}'.format(ret[1]), 'err')
                    return
                response = ' '.join(str(x) for x in ret[1])
                self._log('Response: ' + response, 'ok')

                if 'FF' not in response.upper() and not self.sandbox:
                    self._log('Value is not FF — already patched or wrong mode?', 'err')
                    return

                self._log('Step 2: Writing EEP SET 3961 01 00…', 'dim')
                ret2 = ps3.command('EEP SET 3961 01 00', wait=1)
                if ret2[0] == 0xFFFFFFFF:
                    self._log('Patch write failed: {}'.format(ret2[1]), 'err')
                    return
                self._log('Patch written OK', 'ok')

                self._log('Step 3: Verifying…', 'dim')
                ret3 = ps3.command('EEP GET 3961 01', wait=1)
                response3 = ' '.join(str(x) for x in ret3[1])
                self._log('Verification: ' + response3, 'ok')

                if '00' in response3 or self.sandbox:
                    self._log('CXR->CXRF patch verified! Now: shut down console, connect DIAG to GND, restart in CXRF mode, run Checksum Correction.', 'ok')
                    self._js('onCXRDone()')
                else:
                    self._log('Verification failed — value is not 00', 'err')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Checksum Correction ───────────────────────────────────────────────────

    def checksum_correction(self, port, sc_type):
        def _run():
            try:
                self._log('=== Checksum Correction ===', 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command('eepcsum', wait=1)
                if ret[0] == 0xFFFFFFFF:
                    self._log('eepcsum failed: {}'.format(ret[1]), 'err')
                    return

                if sc_type == 'SW':
                    lines = ''.join(ret[1]).split('\n')
                else:
                    lines = ' '.join(ret[1]).split('\n')

                for line in lines:
                    if line.strip():
                        self._log(line, 'ok')

                corrections = []
                for i, line in enumerate(lines):
                    if 'sum:' in line.lower() and i + 1 < len(lines):
                        m = re.search(
                            r'Addr:\s*0x([0-9a-fA-F]+)\s+should be\s+0x([0-9a-fA-F]+)',
                            lines[i + 1]
                        )
                        if m:
                            addr = m.group(1).upper()[-4:]
                            val  = m.group(2).upper()[-4:]
                            b1 = val[2:4]
                            b2 = val[0:2]
                            corrections.append({
                                'addr': addr,
                                'val':  val,
                                'cmd':  'w {} {} {}'.format(addr, b1, b2),
                            })

                if corrections:
                    self._log('Found {} correction(s) — confirm in UI'.format(len(corrections)), 'warn')
                    self._js('onChecksumData({})'.format(json.dumps(corrections)))
                else:
                    self._log('Checksum OK — no corrections needed', 'ok')
                    self._js('onChecksumOK()')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    def apply_checksum_fix(self, port, sc_type, cmd):
        def _run():
            try:
                self._log('Applying: ' + cmd, 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=1)
                out = ps3.fmt(ret)
                self._log(out, 'ok' if ret[0] != 0xFFFFFFFF else 'err')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Checksum Gate ─────────────────────────────────────────────────────────

    def toggle_checksum_gate(self, port, sc_type, disable):
        def _run():
            try:
                self._log('=== Checksum Gate ===', 'cmd')
                ps3 = self._ps3(port, sc_type)

                self._log('Reading 0x3292…', 'dim')
                ret = ps3.command('r 3292', wait=0.5)
                out = ps3.fmt(ret)
                self._log('Current: ' + out, 'ok')

                target = 'FF' if disable else '00'
                action = 'DISABLING' if disable else 'ENABLING'
                self._log('{} gate -> writing 0x{} to 0x3292…'.format(action, target), 'warn')

                ret2 = ps3.command('w 3292 ' + target, wait=0.5)
                ok = ret2[0] != 0xFFFFFFFF
                self._log(ps3.fmt(ret2), 'ok' if ok else 'err')

                if ok:
                    ret3 = ps3.command('r 3292', wait=0.5)
                    self._log('Verified: ' + ps3.fmt(ret3), 'ok')
                    action_past = 'disabled' if disable else 'enabled'
                    self._log('Checksum gate {} successfully.'.format(action_past), 'ok')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Memory / EEPROM Inspector ─────────────────────────────────────────────

    def read_memory(self, port, sc_type, addr_hex, length_hex):
        def _run():
            try:
                addr   = int(str(addr_hex), 16)
                length = int(str(length_hex), 16)
                if length <= 0 or length > 0x400:
                    self._log('Invalid length (1..0x400)', 'err')
                    self._js('onMemoryData({},[])'.format(json.dumps(addr_hex)))
                    return

                self._log('> read 0x{:04X} ({} bytes)'.format(addr, length), 'cmd')
                ps3 = self._ps3(port, sc_type)

                if sc_type == 'CXRF':
                    cmd = 'r {:04X} {:02X}'.format(addr, length)
                else:
                    cmd = 'EEP GET {:04X} {:02X}'.format(addr, length)

                ret = ps3.command(cmd, wait=1)
                if ret[0] == 0xFFFFFFFF:
                    self._log('Read failed: {}'.format(ret[1]), 'err')
                    self._js('onMemoryData({},[])'.format(json.dumps(addr_hex)))
                    return

                # Flatten and tokenise
                tokens = []
                for item in ret[1]:
                    for piece in str(item).replace('\r', ' ').replace('\n', ' ').split():
                        tokens.append(piece)

                bytes_list = []
                hexset = set('0123456789abcdefABCDEF')
                for tok in tokens:
                    t = tok.strip()
                    # filter out the 8-digit return-code echo and addresses
                    if len(t) == 2 and all(c in hexset for c in t):
                        bytes_list.append(int(t, 16))
                    elif len(t) == 4 and all(c in hexset for c in t):
                        # could be a packed 16-bit word — split into two bytes
                        bytes_list.append(int(t[0:2], 16))
                        bytes_list.append(int(t[2:4], 16))

                # Trim to requested length
                bytes_list = bytes_list[:length]

                self._log('Read {} bytes from 0x{:04X}'.format(len(bytes_list), addr), 'ok')
                self._js('onMemoryData({},{})'.format(
                    json.dumps('{:04X}'.format(addr)),
                    json.dumps(bytes_list)
                ))
            except Exception as e:
                self._log('Read error: {}'.format(e), 'err')
                self._js('onMemoryData({},[])'.format(json.dumps(str(addr_hex))))
        self._thread(_run)
        return {'ok': True}

    # ── Fan table ─────────────────────────────────────────────────────────────

    def fan_read(self, port, sc_type):
        def _run():
            try:
                self._log('Reading fan table…', 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command('fantbl gettable', wait=1)
                out = ps3.fmt(ret)
                self._log(out, 'ok')
                self._js('onFanData({})'.format(json.dumps(out)))
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    # ── Per-chip fan tables (CELL / RSX, 5 phases each) ──────────────────────

    def fan_read_full(self, port, sc_type):
        """Read CELL + RSX fan tables (5 phases each) plus thermal shutdown."""
        def _run():
            try:
                self._log('Reading fan tables (CELL + RSX, 5 phases each)…', 'cmd')
                ps3 = self._ps3(port, sc_type)
                data = {'cell': [], 'rsx': [], 'tshutdown': 85}

                for table_idx, key in enumerate(['cell', 'rsx']):
                    label = key.upper()
                    for p in range(10):
                        cmd = 'fantbl getini {} p{}'.format(table_idx, p)
                        self._log('  ' + cmd, 'dim')
                        ret = ps3.command(cmd, wait=0.4)
                        phase = {'tmin': 0, 'tmax': 0, 'speed': 0}
                        if ret[0] == 0xFFFFFFFF:
                            self._log('  ' + label + ' p{} read failed'.format(p), 'err')
                        else:
                            out = ps3.fmt(ret)
                            # Pull the last 3 integer tokens as TMin / TMax / Speed
                            nums = []
                            for tok in out.replace(',', ' ').split():
                                tok = tok.strip()
                                if tok.startswith('0x') or tok.startswith('0X'):
                                    try: nums.append(int(tok, 16)); continue
                                    except ValueError: pass
                                try: nums.append(int(tok))
                                except ValueError: continue
                            # filter out the 8-digit return-code echo (typically 0)
                            usable = [n for n in nums if n < 0x100]
                            if len(usable) >= 3:
                                phase = {'tmin': usable[-3], 'tmax': usable[-2], 'speed': usable[-1]}
                        data[key].append(phase)

                # Thermal shutdown — single value
                try:
                    ret_ts = ps3.command('tshutdown getini', wait=0.4)
                    if ret_ts[0] != 0xFFFFFFFF:
                        out_ts = ps3.fmt(ret_ts)
                        for tok in out_ts.split():
                            try:
                                v = int(tok)
                                if 50 <= v <= 110:
                                    data['tshutdown'] = v
                                    break
                            except ValueError:
                                pass
                except Exception:
                    pass

                self._log('Fan tables loaded — CELL: {}/10 phases, RSX: {}/10 phases, T-Shutdown: {}°C'.format(
                    len(data['cell']), len(data['rsx']), data['tshutdown']
                ), 'ok')
                self._js('onFanTablesData({})'.format(json.dumps(data)))
            except Exception as e:
                self._log('Fan read error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}

    def fan_write_full(self, port, sc_type, cell, rsx, tshutdown):
        """Write both CELL + RSX tables (5 phases each) and thermal shutdown."""
        def _run():
            try:
                self._log('Writing fan tables…', 'cmd')
                ps3 = self._ps3(port, sc_type)
                for table_idx, (label, phases) in enumerate([('CELL', cell), ('RSX', rsx)]):
                    self._log('--- {} table ---'.format(label), 'dim')
                    for p, ph in enumerate(phases):
                        cmd = 'fantbl setini {} p{} {} {} {}'.format(
                            table_idx, p,
                            int(ph.get('tmin', 0)),
                            int(ph.get('tmax', 0)),
                            int(ph.get('speed', 0)),
                        )
                        self._log('  ' + cmd, 'dim')
                        ret = ps3.command(cmd, wait=0.3)
                        if ret[0] == 0xFFFFFFFF:
                            self._log('Write failed at {} p{}: {}'.format(label, p, ret[1]), 'err')
                            self._js('onFanWriteDone(false)')
                            return
                if tshutdown:
                    ts_cmd = 'tshutdown setini {}'.format(int(tshutdown))
                    self._log('  ' + ts_cmd, 'dim')
                    ps3.command(ts_cmd, wait=0.3)

                self._log('Fan tables written successfully.', 'ok')
                self._js('onFanWriteDone(true)')
            except Exception as e:
                self._log('Fan write error: {}'.format(e), 'err')
                self._js('onFanWriteDone(false)')
        self._thread(_run)
        return {'ok': True}

    # ── Settings (persistent, file-based) ────────────────────────────────────

    def _settings_path(self):
        if getattr(sys, 'frozen', False):
            # PyInstaller exe — write to AppData\Roaming\NostaDiag (always writable)
            base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'NostaDiag')
            os.makedirs(base, exist_ok=True)
        else:
            # Dev mode — write next to app_web.py
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, 'settings.json')

    def settings_load(self):
        try:
            with open(self._settings_path(), 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def settings_save(self, data):
        try:
            with open(self._settings_path(), 'w') as f:
                json.dump(data, f, indent=2)
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'err': str(e)}

    # ── Undervolt ─────────────────────────────────────────────────────────────

    def undervolt_apply(self, port, sc_type, chip, nm, mode):
        """Apply or restore CELL/RSX voltage preset."""
        PRESETS = {
            'cell': {
                'stock':     {'90nm': ('w 50 39', '1.2250V'), '65nm': ('w 50 3E', '1.1000V'), '45nm': ('w 50 25', '0.9500V')},
                'undervolt': {'90nm': ('w 50 1D', '1.1375V'), '65nm': ('w 50 3E', '1.1000V'), '45nm': ('w 50 07', '0.9125V')},
            },
            'rsx': {
                'stock':     {'90nm': ('w 51 36', '1.3000V'), '65nm': ('w 51 3E', '1.1000V'), '40nm': ('w 51 25', '0.9500V')},
                'undervolt': {'90nm': ('w 51 1B', '1.1875V'), '65nm': ('w 51 00', '1.0875V'), '40nm': ('w 51 07', '0.9125V')},
            },
        }
        table = PRESETS.get(chip, {}).get(mode, {})
        entry = table.get(nm)
        if not entry:
            self._log('Unknown combination: {}/{}/{}'.format(chip.upper(), nm, mode), 'err')
            return {'ok': False}
        cmd, voltage = entry
        label = '{} {}nm ({})'.format(chip.upper(), nm.replace('nm', ''), mode.replace('undervolt', 'UV').upper())

        def _run():
            try:
                self._log('=== {} ==='.format(label), 'cmd')
                self._log('Voltage: {}  Command: {}'.format(voltage, cmd), 'dim')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=1)
                ok = ret[0] != 0xFFFFFFFF
                out = ps3.fmt(ret)
                self._log(out, 'ok' if ok else 'err')
                if ok:
                    self._log('{} applied — voltage: {}'.format(label, voltage), 'ok')
                    self._js('onUndervoltDone(true,{})'.format(json.dumps('{} at {}'.format(label, voltage))))
                else:
                    self._js('onUndervoltDone(false,{})'.format(json.dumps(out)))
            except Exception as e:
                self._log('Undervolt error: {}'.format(e), 'err')
                self._js('onUndervoltDone(false,{})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    def undervolt_manual(self, port, sc_type, chip, hex_val):
        """Apply a manually specified voltage to CELL (addr 50) or RSX (addr 51)."""
        addr = '50' if chip == 'cell' else '51'
        cmd = 'w {} {}'.format(addr, hex_val.upper())
        label = '{} manual'.format(chip.upper())

        def _run():
            try:
                self._log('=== {} ===  Command: {}'.format(label, cmd), 'cmd')
                ps3 = self._ps3(port, sc_type)
                ret = ps3.command(cmd, wait=1)
                ok = ret[0] != 0xFFFFFFFF
                out = ps3.fmt(ret)
                self._log(out, 'ok' if ok else 'err')
                if ok:
                    self._log('{} voltage applied'.format(label), 'ok')
                    self._js('onUndervoltDone(true,{})'.format(json.dumps(label + ' applied')))
                else:
                    self._js('onUndervoltDone(false,{})'.format(json.dumps(out)))
            except Exception as e:
                self._log('Undervolt error: {}'.format(e), 'err')
                self._js('onUndervoltDone(false,{})'.format(json.dumps(str(e))))
        self._thread(_run)
        return {'ok': True}

    def fan_write(self, port, sc_type, speeds):
        BASE_TEMPS = [30, 40, 50, 60, 65, 70, 75, 80, 85, 90]

        def _run():
            try:
                self._log('Writing fan table…', 'cmd')
                ps3 = self._ps3(port, sc_type)
                for i, (temp, speed) in enumerate(zip(BASE_TEMPS, speeds)):
                    cmd = 'fantbl set {} {} {}'.format(i, temp, int(speed))
                    self._log('  ' + cmd, 'dim')
                    ret = ps3.command(cmd, wait=0.3)
                    if ret[0] == 0xFFFFFFFF:
                        self._log('Failed at point {}'.format(i), 'err')
                        return
                self._log('Fan table written successfully', 'ok')
            except Exception as e:
                self._log('Error: {}'.format(e), 'err')
        self._thread(_run)
        return {'ok': True}


# ── Entry point ───────────────────────────────────────────────────────────────

def _start_local_server(directory, settings_path_fn):
    """Spawn a tiny HTTP server on localhost so the WebView can load files
    via http:// — bypasses Edge/WebView2's file:// quirks with relative paths
    across directories (../assets/…) which break in PyInstaller bundles.

    Also handles GET /reset-settings — deletes settings.json and restarts the
    process.  JS can call this even when the pywebview bridge is not yet ready,
    because the request goes to the same origin (relative URL).
    """
    import http.server
    import socketserver

    def _do_restart():
        import time as _time
        _time.sleep(0.8)
        try:
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception:
            pass
        os._exit(0)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt, *args):
            pass  # silence per-request console noise

        def do_GET(self):
            if self.path == '/reset-settings':
                self._handle_reset()
                return
            if self.path == '/mode.json':
                self._handle_mode()
                return
            super().do_GET()

        def _handle_mode(self):
            """Return just the lightMode flag so the page can apply the
            correct theme class before first render — no bridge needed."""
            try:
                with open(settings_path_fn(), 'r') as f:
                    data = json.load(f)
                light = data.get('lightMode', True)
            except Exception:
                light = True
            body = json.dumps({'lightMode': bool(light)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_reset(self):
            # Delete settings.json (ignore errors)
            try:
                sp = settings_path_fn()
                if os.path.exists(sp):
                    os.remove(sp)
            except Exception:
                pass
            body = b'Settings deleted. Restarting...'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=_do_restart, daemon=True).start()

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


def main():
    api = Api()
    base_dir  = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_path = resource_path(os.path.join('assets', 'logo.ico'))

    # Local HTTP server — serves the whole project tree so relative
    # paths like ../assets/foo.jpg resolve correctly in dev AND in the bundled .exe
    port = _start_local_server(base_dir, api._settings_path)
    url  = 'http://127.0.0.1:{}/webui/index.html'.format(port)

    kwargs = dict(
        url=url,
        js_api=api,
        width=1440,
        height=900,
        min_size=(960, 640),
    )
    try:
        window = webview.create_window(
            'NostaDiag — PS3 Syscon Diagnostic Tool',
            icon=icon_path,
            **kwargs,
        )
    except TypeError:
        window = webview.create_window(
            'NostaDiag — PS3 Syscon Diagnostic Tool',
            **kwargs,
        )

    api.window = window

    try:
        webview.start(debug=False, icon=icon_path)
    except TypeError:
        webview.start(debug=False)


if __name__ == '__main__':
    main()
