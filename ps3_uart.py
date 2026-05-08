from binascii import unhexlify as uhx
from Cryptodome.Cipher import AES
import os
import sys
import string
import time
import re


def _resource_path(rel_path):
    """Find a bundled resource — works both in dev and in a PyInstaller bundle."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

_SANDBOX_STATE = {}
_SANDBOX_DB    = {}

PS3_ERROR_DB = {
    "A0401001": ("BE_VRAM_POWER_FAIL",  "Cell VRAM power failure -> check VRM & caps near Cell processor"),
    "A0401002": ("RSX_VRAM_POWER_FAIL", "RSX VRAM power failure -> check VRM & caps near RSX GPU"),
    "A0801001": ("BE_VRM_FAIL",         "Cell voltage regulator failure -> faulty VRM module or caps"),
    "A0801002": ("RSX_VRM_FAIL",        "RSX voltage regulator failure -> faulty VRM module or caps"),
    "A0201001": ("BE_THERMAL_FAIL",     "Cell overtemperature/thermal fault -> repaste & clean fan"),
    "A0201002": ("RSX_THERMAL_FAIL",    "RSX overtemperature/thermal fault -> repaste & clean fan"),
    "A0101001": ("BE_POWER_FAIL",       "Cell main power failure -> check PSU & power rail"),
    "A0101002": ("RSX_POWER_FAIL",      "RSX main power failure -> check PSU & power rail"),
    "A0601001": ("BE_PLL_FAIL",         "Cell PLL/clock failure -> possible cold solder or RSX damage"),
    "A0601002": ("RSX_PLL_FAIL",        "RSX PLL/clock failure -> RSX or interconnect issue"),
    "A0301001": ("BE_BOOT_FAIL",        "Cell boot failure -> corrupted firmware or hardware fault"),
    "A0301002": ("RSX_BOOT_FAIL",       "RSX boot failure -> corrupted firmware or hardware fault"),
    "A0501001": ("BE_SCEI_FAIL",        "Cell SCEI security failure -> possible auth/firmware issue"),
    "A0501002": ("RSX_SCEI_FAIL",       "RSX SCEI failure -> possible auth/firmware issue"),
    "A0701001": ("BE_EXT_FAIL",         "Cell external fault -> check XDR RAM"),
    "A0701002": ("RSX_EXT_FAIL",        "RSX external fault -> check GDDR3 VRAM"),
    "1001":     ("CPU Error",           "Cell processor fault -> reflow or replace NEC/Tokin caps"),
    "1002":     ("GPU Error",           "RSX GPU fault -> reflow or replace NEC/Tokin caps"),
    "1003":     ("CPU+GPU Error",       "Both Cell & RSX fault -> reflow, check NEC/Tokin caps"),
    "1200":     ("Overheat",            "Console overheated -> clean fan & heatsink, repaste"),
    "1201":     ("Fan Fault",           "Fan not spinning or sensor error -> check fan connector"),
    "1202":     ("Overheat (RSX)",      "RSX temperature too high -> repaste RSX"),
    "1700":     ("HDD Error",           "Hard drive communication failure -> reseat or replace HDD"),
    "1701":     ("HDD Not Found",       "No HDD detected -> reseat or replace HDD"),
    "1800":     ("BD Drive Error",      "Blu-ray drive fault -> replace BD drive or laser"),
    "3002":     ("BD Auth Fail",        "Blu-ray disc authentication error -> clean disc/lens"),
    "80010514": ("Disc Read Error",     "Blu-ray read failure -> clean lens or replace BD drive"),
    "8002F14E": ("Update Failure",      "Firmware update error -> try different USB or reformat"),
    "8001003D": ("No HDD",             "HDD missing or not formatted -> insert/format HDD"),
    "80029564": ("NP Error",            "PlayStation Network error -> check internet connection"),
    "8002A537": ("NP Timeout",          "PSN connection timeout -> check NAT type & router"),
    "8002A548": ("NP Disconnected",     "PSN connection lost -> check internet connection"),
    "80022D11": ("BD Drive Error",      "Blu-ray drive internal error -> replace BD drive"),
    "80010017": ("Save Corrupt",        "Save data corrupt -> delete save data"),
    "8002B241": ("DRM Error",           "Content license issue -> restore licences in Account Mgmt"),
}

def _ps3_annotate(line: str) -> str:
    upper = line.upper()
    for code, (label, desc) in PS3_ERROR_DB.items():
        if code.upper() in upper:
            return f"  > [{label}] {desc}"
    return ""


class PS3UART:
    def __init__(self, port, sc_type, serial_speed, sandbox_mode=False):
        self.sandbox_mode = sandbox_mode

        if not sandbox_mode:
            try:
                import serial
            except ImportError:
                raise RuntimeError("pyserial is required: pip install pyserial")

        self.port = port
        self.sc_type = sc_type
        self.serial_speed = serial_speed

        if not sandbox_mode:
            import serial as _serial
            self.ser = _serial.Serial()
        else:
            self.ser = None

        self.sc2tb = uhx('71f03f184c01c5ebc3f6a22a42ba9525')
        self.tb2sc = uhx('907e730f4d4e0a0b7b75f030eb1d9d36')
        self.value = uhx('3350BD7820345C29056A223BA220B323')
        self.zero  = uhx('00000000000000000000000000000000')

        self.auth1r_header = uhx('10100000FFFFFFFF0000000000000000')
        self.auth2_header  = uhx('10010000000000000000000000000000')

        if not sandbox_mode:
            self.ser.port = port
            if serial_speed == '57600':
                self.ser.baudrate = 57600
            elif serial_speed == '115200':
                self.ser.baudrate = 115200
            else:
                raise ValueError(f"Invalid serial speed: {serial_speed}")
            self.type = sc_type
            self.ser.timeout = 0.1
            self.ser.open()
            assert self.ser.isOpen()
            self.ser.flush()
        else:
            self.type = sc_type

    def aes_decrypt_cbc(self, key, iv, data):
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(data)

    def aes_encrypt_cbc(self, key, iv, data):
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(data)

    def __del__(self):
        if not self.sandbox_mode and self.ser:
            try:
                self.ser.close()
            except Exception:
                pass

    def send(self, data):
        if self.sandbox_mode:
            print(f"[SANDBOX] Sending: {data}")
        else:
            self.ser.write(data.encode('ascii'))

    def receive(self):
        if self.sandbox_mode:
            return b"w complete!\n[mullion]$"
        if hasattr(self, 'type') and self.type == 'CXRF':
            start = time.time()
            buffer = b''
            while time.time() - start < 2.0:
                waiting = self.ser.inWaiting()
                if waiting > 0:
                    chunk = self.ser.read(waiting)
                    buffer += chunk
                    if b'[mullion]$' in buffer or b'SC_READY' in buffer:
                        break
                time.sleep(0.05)
            return buffer if buffer else self.ser.read(self.ser.inWaiting())
        else:
            return self.ser.read(self.ser.inWaiting())

    def command(self, com, wait=1, verbose=False):
        if verbose:
            print('Command: ' + com)

        if self.sandbox_mode:
            print(f"[SANDBOX] Command: {com}")
            time.sleep(0.1)
            global _SANDBOX_DB, _SANDBOX_STATE
            if not _SANDBOX_DB:
                try:
                    import json as _json
                    _sb_path = _resource_path("sandbox_data.json")
                    if os.path.exists(_sb_path):
                        with open(_sb_path, 'r', encoding='utf-8') as _f:
                            _SANDBOX_DB = _json.load(_f)
                except Exception as _e:
                    print(f"[SANDBOX] sandbox_data.json error: {_e}")

            com_strip = com.strip()
            com_lower = com_strip.lower()

            _write_prefixes = ('w ', 'w16 ', 'w32 ', 'fantbl set', 'tshutdown set', 'clearerrlog')
            if any(com_lower.startswith(p) for p in _write_prefixes):
                parts = com_strip.split()
                if parts[0].lower() in ('w', 'w16', 'w32') and len(parts) >= 3:
                    addr = parts[1].upper()
                    val  = parts[2].upper()
                    _SANDBOX_STATE[f"r {addr}"] = f"00000000 {val}"
                return (0, ["Complete!"])

            _read_prefixes = ('r ', 'r16 ', 'r32 ')
            if any(com_lower.startswith(p) for p in _read_prefixes):
                parts = com_strip.split()
                if len(parts) >= 2:
                    key = f"r {parts[1].upper()}"
                    if key in _SANDBOX_STATE:
                        resp = _SANDBOX_STATE[key]
                        p = resp.split(' ', 1)
                        return (int(p[0], 16), [p[1]] if len(p) > 1 else [])

            if com_lower in ('auth', 'auth1', 'auth2') or com_lower.startswith('auth1 '):
                return (0, ["Auth successful"])

            response = None
            if com_lower in _SANDBOX_DB:
                response = _SANDBOX_DB[com_lower]
            else:
                for key in _SANDBOX_DB:
                    if key.startswith('_'):
                        continue
                    if com_lower.startswith(key.lower()):
                        response = _SANDBOX_DB[key]
                        break

            if response is not None:
                if response == "Auth successful":
                    return (0, ["Auth successful"])
                parts = response.split(' ', 1)
                try:
                    ret_code = int(parts[0], 16)
                except ValueError:
                    ret_code = 0
                ret_data = [parts[1]] if len(parts) > 1 else []
                return (ret_code, ret_data)

            return (0, ["Complete!"])

        if self.type == 'CXR':
            length = len(com)
            checksum = sum(bytearray(com, 'ascii')) % 0x100
            if length <= 10:
                self.send('C:{:02X}:{}\r\n'.format(checksum, com))
            else:
                j = 10
                self.send('C:{:02X}:{}'.format(checksum, com[0:j]))
                for i in range(length - j, 15, -15):
                    self.send(com[j:j+15])
                    j += 15
                self.send(com[j:] + '\r\n')
        elif self.type == 'SW':
            length = len(com)
            if length >= 0x40:
                if self.command('SETCMDLONG FF FF')[0] != 0:
                    return (0xFFFFFFFF, ['Setcmdlong'])
            checksum = sum(bytearray(com, 'ascii')) % 0x100
            self.send('{}:{:02X}\r\n'.format(com, checksum))
        else:
            self.send(com + '\r\n')

        time.sleep(wait)
        answer = self.receive().decode('ascii', 'ignore').strip()
        if verbose:
            print('Answer: ' + answer)

        if self.type == 'CXR':
            answer = answer.split(':')
            if len(answer) != 3:
                return (0xFFFFFFFF, ['Answer length'])
            checksum = sum(bytearray(answer[2], 'ascii')) % 0x100
            if answer[0] not in ('R', 'E'):
                return (0xFFFFFFFF, ['Magic'])
            if answer[1] != '{:02X}'.format(checksum):
                return (0xFFFFFFFF, ['Checksum'])
            data = answer[2].split(' ')
            if (answer[0] == 'R' and len(data) < 2) or (answer[0] == 'E' and len(data) != 2):
                return (0xFFFFFFFF, ['Data length'])
            if data[0] != 'OK' or len(data) < 2:
                return (int(data[1], 16), [])
            else:
                return (int(data[1], 16), data[2:])
        elif self.type == 'SW':
            answer = answer.split('\n')
            for i in range(len(answer)):
                answer[i] = answer[i].replace('\n', '').rsplit(':', 1)
                if len(answer[i]) != 2:
                    return (0xFFFFFFFF, ['Answer length'])
                checksum = sum(bytearray(answer[i][0], 'ascii')) % 0x100
                if answer[i][1] != '{:02X}'.format(checksum):
                    return (0xFFFFFFFF, ['Checksum'])
                answer[i][0] += '\n'
            ret = answer[-1][0].replace('\n', '').split(' ')
            if len(ret) < 2 or (len(ret[1]) != 8 and not all(c in string.hexdigits for c in ret[1])):
                return (0, [x[0] for x in answer])
            elif len(answer) == 1:
                return (int(ret[1], 16), ret[2:])
            else:
                return (int(ret[1], 16), [x[0] for x in answer[:-1]])
        else:
            return (0, [answer])

    def auth(self):
        if self.sandbox_mode:
            return 'Auth successful (Sandbox Mode)'

        if self.type in ('CXR', 'SW'):
            auth1r = self.command('AUTH1 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')
            if auth1r[0] == 0 and auth1r[1] != []:
                auth1r = uhx(auth1r[1][0])
                if auth1r[0:0x10] == self.auth1r_header:
                    data = self.aes_decrypt_cbc(self.sc2tb, self.zero, auth1r[0x10:0x40])
                    if data[0x8:0x10] == self.zero[0x0:0x8] and data[0x10:0x20] == self.value and data[0x20:0x30] == self.zero:
                        new_data = data[0x8:0x10] + data[0x0:0x8] + self.zero + self.zero
                        auth2_body = self.aes_encrypt_cbc(self.tb2sc, self.zero, new_data)
                        auth2r = self.command('AUTH2 ' + ''.join('{:02X}'.format(c) for c in bytearray(self.auth2_header + auth2_body)))
                        if auth2r[0] == 0:
                            return 'Auth successful'
                        else:
                            return 'Auth failed'
                    else:
                        return 'Auth1 response body invalid'
                else:
                    return 'Auth1 response header invalid'
            else:
                return 'Auth1 response invalid'
        else:
            scopen = self.command('scopen')
            if 'SC_READY' in scopen[1][0]:
                auth1r = self.command('10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')
                auth1r = auth1r[1][0].split('\r')[1][1:]
                if len(auth1r) == 128:
                    auth1r = uhx(auth1r)
                    if auth1r[0:0x10] == self.auth1r_header:
                        data = self.aes_decrypt_cbc(self.sc2tb, self.zero, auth1r[0x10:0x40])
                        if data[0x8:0x10] == self.zero[0x0:0x8] and data[0x10:0x20] == self.value and data[0x20:0x30] == self.zero:
                            new_data = data[0x8:0x10] + data[0x0:0x8] + self.zero + self.zero
                            auth2_body = self.aes_encrypt_cbc(self.tb2sc, self.zero, new_data)
                            auth2r = self.command(''.join('{:02X}'.format(c) for c in bytearray(self.auth2_header + auth2_body)))
                            if 'SC_SUCCESS' in auth2r[1][0]:
                                return 'Auth successful'
                            else:
                                return 'Auth failed'
                        else:
                            return 'Auth1 response body invalid'
                    else:
                        return 'Auth1 response header invalid'
                else:
                    return 'Auth1 response invalid'
            else:
                return 'scopen response invalid'

    def fmt(self, ret):
        """Format command result to string."""
        if ret[0] == 0xFFFFFFFF:
            return f"ERROR: {ret[1][0] if ret[1] else 'unknown error'}"
        if self.type in ('CXR', 'CXRF'):
            return '{:08X} {}'.format(ret[0], ' '.join(ret[1]))
        elif self.type == 'SW':
            if ret[1] and '\n' not in ret[1][0]:
                return '{:08X} {}'.format(ret[0], ' '.join(ret[1]))
            else:
                return '{:08X}\n{}'.format(ret[0], ''.join(ret[1]))
        return ret[1][0] if ret[1] else str(ret[0])
