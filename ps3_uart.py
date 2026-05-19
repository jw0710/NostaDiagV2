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
    # ── Long-form syscon hardware fault codes ────────────────────────────────
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

    # ── System Errors (1xxx) ─────────────────────────────────────────────────
    "1001": ("Power Cell",              "Insufficient filtering on CELL VDDC or unexpected shutdown -> alone is common on healthy machines; check CELL NEC/TOKIN caps only if YLOD occurs under load"),
    "1002": ("Power RSX",               "Insufficient filtering on RSX_VDDC -> fingerprint of bad NEC/TOKIN caps on RSX power block; check NEC/TOKINs near RSX"),
    "1004": ("Power AC/DC",             "AC power loss or forced power-off (cord pulled/rocker switch) -> can be ignored if not from normal shutdown; check PSU if recurring"),
    "1103": ("Thermal Alert System",    "Thermal alert signal from CELL or CELL temp monitor -> Mullion syscon only; overheating in CELL or associated monitor chip"),
    "1200": ("Thermal Cell",            "Cell CPU overheat -> replace TIM between IHS and heatsink; check fan & CELL thermal monitor chip; rarely a dead CPU"),
    "1201": ("Thermal RSX",             "RSX GPU overheat -> replace TIM; very rare under normal use (RSX fails before TIM degrades); check RSX thermal monitor chip"),
    "1203": ("Thermal Cell VR",         "CELL VR thermal fault -> only on boards with a CELL power block temp monitor (TMU-520/COK-001/COK-002); check VRM area"),
    "1204": ("Thermal South Bridge",    "South Bridge overtemperature -> check SB cooling & board"),
    "1205": ("Thermal EE/GS",           "EE/GS chip overheat -> COK-001 (CXD2953AGB, full PS2: EE+GS) or COK-002 (CXD2972GB, partial PS2: GS only) models only"),
    "1301": ("CELL PLL Unlock",         "CELL PLL/clock unlock -> CPU damage from delid attempt, failed reball, or excessive heat; often precedes 3034/4xxx"),
    "14FF": ("Check Stop",              "Critical hardware halt (impossible CPU/GPU state) -> most likely failing RSX BGA/bump solder joint; console shuts down paired with 1701"),
    "1601": ("CELL Livelock Detection", "CELL deadlocked by RSX solder joint failure -> early stage of RSX BGA/bump defect; precedes 3034 when solder fully cracks; less likely CELL"),
    "1701": ("CELL BE Attention",       "CELL BE ATTENTION signal raised -> triggered by 14FF, 1601, or 1301; also: BGA/bump defect while powered on, damaged HDD, or homebrew conflict"),
    "1802": ("RSX Initialization",      "RSX init failure -> A020xxxx: RSX completely dead or absent (step 20); A080xxxx: RSX interrupt caused a checkstop during operation"),
    "1900": ("RTC Voltage",             "RTC battery voltage issue -> check/replace CMOS battery"),
    "1901": ("RTC Oscillator",          "RTC oscillator fault -> check RTC crystal & circuit"),
    "1902": ("RTC Access",              "RTC access error -> check RTC chip & battery connection"),

    # ── Fatal Errors (2xxx) ──────────────────────────────────────────────────
    # 3 groups (20xx, 21xx, 22xx) — second digit meaning unknown; same components repeat across groups
    "2001": ("Fatal CELL",                  "Fatal CELL error -> distinct from 1001; check Cell processor & surrounding hardware"),
    "2002": ("Fatal RSX",                   "Fatal RSX error -> distinct from 1002; check RSX GPU & GDDR3 VRAM"),
    "2003": ("Fatal South Bridge",          "Fatal South Bridge error -> check SB & board I/O"),
    "2010": ("Fatal Clock Subsystems",      "Clock generator failure (5V_MISC supply) -> check 5V rail fuse; shorted cap on 5V rail can cut power to CPU/GPU/SB"),
    "2011": ("Fatal Clock Cell",            "Clock generator failure (CELL clock) -> check CELL clock supply"),
    "2012": ("Fatal Clock Cell (2)",        "Clock generator failure (CELL clock variant) -> check CELL clock supply"),
    "2013": ("Fatal Clock Cell/RSX/SB",     "Clock generator failure (XDR/FlexIO PLL) -> check +1.2V_YC_RC_VDDIO rail fuse; common combo with 2120"),
    "2020": ("Fatal HDMI",                  "HDMI transmitter failure -> check +1.7V_MISC supply, VDDIO rail fuse, and thermistor near HDMI chip; RSX/CELL VDDIO BGA defects can cause this"),
    "2022": ("Fatal DVE",                   "DVE/MultiAV encoder failure -> can cause delayed YLOD (10s–1min), GLOD, or RLOD"),
    "2024": ("Fatal AV",                    "AV output failure -> replace AV and/or HDMI encoder chip; causes delayed YLOD; 2024 & 2124 often occur together"),
    "2030": ("Fatal Thermal Sensor Cell",   "CELL thermal sensor fault -> check CELL thermal monitor chip; also check PWR/EJT daughter board"),
    "2031": ("Fatal Thermal Sensor RSX",    "RSX thermal sensor fault -> check RSX thermal monitor chip"),
    "2033": ("Fatal Thermal Sensor SB",     "South Bridge thermal sensor fault -> check SB thermal monitor chip"),
    "2101": ("Fatal CELL (2)",              "Fatal CELL error group 2 -> check Cell processor; NEC/TOKIN short has been known to cause this"),
    "2102": ("Fatal RSX (2)",               "Fatal RSX error group 2 -> check RSX; removing NEC/TOKIN short has been known to clear this"),
    "2103": ("Fatal South Bridge (2)",      "Fatal South Bridge error group 2 -> check SB & board I/O"),
    "2110": ("Fatal Clock Subsystems (2)",  "Clock generator failure group 2 (5V_MISC supply) -> check 5V rail fuse; shorted cap on 5V rail can cut power to CPU/GPU/SB"),
    "2111": ("Fatal Clock Cell (2-1)",      "Clock generator failure group 2 (CELL clock) -> check CELL clock supply"),
    "2112": ("Fatal Clock Cell (2-2)",      "Clock generator failure group 2 (CELL clock variant) -> check CELL clock supply"),
    "2113": ("Fatal Clock Multi (2)",       "Clock generator failure group 2 (XDR/FlexIO PLL) -> check VDDIO rail fuse; common A020/A021 combo with 2120"),
    "2120": ("Fatal HDMI (2)",              "HDMI transmitter failure group 2 -> check +1.7V_MISC, VDDIO rail fuse, thermistor near HDMI; RSX VDDIO BGA defects confirmed cause"),
    "2122": ("Fatal DVE (2)",               "DVE/MultiAV encoder failure group 2 -> can cause delayed YLOD/GLOD/RLOD"),
    "2124": ("Fatal AV (2)",                "AV output failure group 2 -> replace AV and/or HDMI encoder chip; 2124 & 2024 often occur together"),
    "2130": ("Fatal Therm Sensor Cell (2)", "CELL thermal sensor fault group 2 -> check CELL thermal monitor chip; also PWR/EJT daughter board"),
    "2131": ("Fatal Therm Sensor RSX (2)",  "RSX thermal sensor fault group 2 -> check RSX thermal monitor chip"),
    "2133": ("Fatal Therm Sensor SB (2)",   "South Bridge thermal sensor fault group 2 -> check SB thermal monitor chip"),
    "2203": ("Fatal South Bridge (3)",      "South Bridge fault group 3 -> related to SB PLL supply (+2.5V_SB_PLL_VDDC) or SB DDR rail (+1.2V_SB_VDDR); check SB power rails"),
    "2310": ("Fatal 12V Power Fail",        "12V power failure -> usually bad PSU; check 12V_main line for shorts; measure 12V connector resistance (should read kΩ range)"),

    # ── Fatal Boot Errors (3xxx) ─────────────────────────────────────────────
    "3000": ("Boot Power Failure",      "Power failure at boot -> check PSU & all power rails"),
    "3001": ("Boot 12V Power Failure",  "12V power failure at boot -> bad PSU; check 12V_main line fuses & caps for shorts"),
    "3002": ("Boot Power Failure (2)",  "Power failure at boot -> check PSU & power rails"),
    "3003": ("CELL Core Power Fail",    "CELL core VDDC power failure at boot -> severely damaged NEC/TOKIN caps on CELL power block; also check for shorted BD drive"),
    "3004": ("RSX Core Power Fail",     "RSX core VDDC power failure at boot -> severely damaged NEC/TOKIN caps on RSX power block"),
    "3010": ("Boot CELL Error",         "CELL error at boot -> related to CPU Buck Controller PWRGD signal; check CELL VRM & power-good line"),
    "3011": ("Boot CELL Error (2)",     "CELL error at boot -> check Cell processor & boot sequence"),
    "3012": ("Boot CELL Error (3)",     "CELL error at boot -> check Cell processor & boot sequence"),
    "3013": ("Boot BE SPI Error",       "CELL not communicating with SYSCON via SPI (BE_SPI DI/DO error) -> check 1.2V MC2_VDDIO & 1.2V BE_VCS rails; possible dead CELL"),
    "3020": ("Boot CELL Error (4)",     "CELL error at boot -> check Cell init & clock/power subsystems"),
    "3030": ("Boot CELL Error (5)",     "CELL error at boot -> check Cell init sequence"),
    "3031": ("Boot CELL Error (6)",     "CELL error at boot -> check Cell init sequence"),
    "3032": ("Boot CELL VDDA Fail",     "CELL boot error caused by missing +1.5V_YC_RC_VDDA -> check VDDA power rail & associated DC-DC converter"),
    "3033": ("Boot CELL Error (7)",     "CELL error at boot -> check Cell init sequence"),
    "3034": ("Boot CELL-RSX Comm Fail", "CELL/RSX FlexIO communication failure (BitTraining) -> BGA/bump solder defect, primarily RSX; main cause of YLOD; reball/reflow RSX"),
    "3035": ("Boot CELL+RSX Error",     "CELL and RSX error at boot -> check RSX & CELL BGA/bump solder joints"),
    "3036": ("Boot CELL+RSX Error (2)", "CELL and RSX error at boot -> check RSX & CELL BGA/bump solder joints"),
    "3037": ("Boot CELL+RSX Error (3)", "CELL and RSX error at boot -> check RSX & CELL FlexIO interconnect"),
    "3038": ("Boot CELL+RSX Error (4)", "CELL and RSX error at boot -> check RSX & CELL FlexIO interconnect"),
    "3039": ("Boot CELL+RSX Error (5)", "CELL and RSX error at boot -> check RSX & CELL FlexIO interconnect"),
    "3040": ("Boot Flash Error",        "Flash (NAND/NOR) error at boot step 60 (StarShip2 init) -> flash not powered or not soldered properly; check flash voltages & firmware integrity"),

    # ── Data Errors (4xxx) ───────────────────────────────────────────────────
    # 5 groups (40xx–44xx); second digit meaning unknown; same components repeat
    # Component mapping per wiki: x01=CELL, x02=RSX, x03=SB, x11=CELL, x12=RSX, x21=CELL, x22=RSX, x31=CELL, x32=RSX, x41=CELL
    # 44xx group = CELL or RSX (SPI data line broken by BGA/bump defect, often paired with 3034)
    "4001": ("Data Err Cell",           "CELL SPI/FlexIO data error (group 1) -> check CELL SPI interface & NAND/NOR flash"),
    "4002": ("Data Err RSX",            "RSX SPI/FlexIO data error (group 1) -> broken SPI data line from RSX BGA/bump defect; often paired with 3034"),
    "4003": ("Data Err South Bridge",   "South Bridge SPI data error (group 1) -> check SB SPI lines"),
    "4011": ("Data Err Cell (1b)",      "CELL SPI data error (group 1b) -> check CELL SPI interface & flash"),
    "4101": ("Data Err Cell (2)",       "CELL SPI/FlexIO data error (group 2) -> check CELL SPI interface & flash"),
    "4102": ("Data Err RSX (2)",        "RSX SPI/FlexIO data error (group 2) -> check RSX SPI lines; RSX BGA/bump defect"),
    "4103": ("Data Err SB (2)",         "South Bridge SPI data error (group 2) -> check SB"),
    "4111": ("Data Err Cell (2b)",      "CELL SPI data error (group 2b) -> check CELL SPI interface & flash"),
    "4201": ("Data Err Cell (3)",       "CELL SPI/FlexIO data error (group 3) -> check CELL SPI interface & flash"),
    "4202": ("Data Err RSX (3)",        "RSX SPI/FlexIO data error (group 3) -> check RSX SPI lines; RSX BGA/bump defect"),
    "4203": ("Data Err SB (3)",         "South Bridge SPI data error (group 3) -> check SB"),
    "4211": ("Data Err Cell (3b)",      "CELL SPI data error (group 3b) -> check CELL SPI interface"),
    "4212": ("Data Err RSX (3b)",       "RSX SPI data error (group 3b) -> check RSX SPI lines"),
    "4221": ("Data Err Cell (3c)",      "CELL SPI data error (group 3c) -> check CELL SPI interface"),
    "4222": ("Data Err RSX (3c)",       "RSX SPI data error (group 3c) -> check RSX SPI lines"),
    "4231": ("Data Err Cell (3d)",      "CELL SPI data error (group 3d) -> check CELL SPI interface"),
    "4261": ("Data Err Cell (3e)",      "CELL SPI data error (group 3e) -> check CELL SPI interface"),
    "4301": ("Data Err Cell (4)",       "CELL SPI/FlexIO data error (group 4) -> check CELL SPI interface & flash"),
    "4302": ("Data Err RSX (4)",        "RSX SPI/FlexIO data error (group 4) -> check RSX SPI lines; RSX BGA/bump defect"),
    "4303": ("Data Err SB (4)",         "South Bridge SPI data error (group 4) -> check SB"),
    "4311": ("Data Err Cell (4b)",      "CELL SPI data error (group 4b) -> check CELL SPI interface"),
    "4312": ("Data Err RSX (4b)",       "RSX SPI data error (group 4b) -> check RSX SPI lines"),
    "4321": ("Data Err Cell (4c)",      "CELL SPI data error (group 4c) -> check CELL SPI interface"),
    "4322": ("Data Err RSX (4c)",       "RSX SPI data error (group 4c) -> check RSX SPI lines"),
    "4332": ("Data Err RSX (4d)",       "RSX SPI data error (group 4d) -> check RSX SPI lines"),
    "4341": ("Data Err Cell (4e)",      "CELL SPI data error (group 4e) -> check CELL SPI interface"),
    "4401": ("Data Err Cell/RSX",       "CELL or RSX SPI data error (group 5) -> SPI line broken by BGA/bump defect; commonly paired with 3034 (YLOD)"),
    "4402": ("Data Err Cell/RSX (2)",   "CELL or RSX SPI data error (group 5b) -> SPI line broken by BGA/bump defect; check RSX & CELL interconnect"),
    "4403": ("Data Err Cell/RSX (3)",   "CELL or RSX SPI data error (group 5c) -> SPI line broken by BGA/bump defect; check RSX & CELL"),
    "4411": ("Data Err Cell/RSX (4)",   "CELL or RSX SPI data error (group 5d) -> check RSX & CELL SPI interface"),
    "4412": ("Data Err Cell/RSX (5)",   "CELL or RSX SPI data error (group 5e) -> check RSX & CELL SPI lines"),
    "4421": ("Data Err Cell/RSX (6)",   "CELL or RSX SPI data error (group 5f) -> check RSX & CELL SPI lines"),
    "4422": ("Data Err Cell/RSX (7)",   "CELL or RSX SPI data error (group 5g) -> check RSX & CELL SPI lines"),
    "4432": ("Data Err Cell/RSX (8)",   "CELL or RSX SPI data error (group 5h) -> check RSX & CELL SPI lines"),
    "4441": ("Data Err Cell/RSX (9)",   "CELL or RSX SPI data error (group 5i) -> check RSX & CELL SPI interface"),

    # ── XMB / System Software Error Codes ────────────────────────────────────
    "80010514": ("Disc Read Error",  "Blu-ray read failure -> clean lens or replace BD drive"),
    "8002F14E": ("Update Failure",   "Firmware update error -> try different USB or reformat"),
    "8001003D": ("No HDD",           "HDD missing or not formatted -> insert/format HDD"),
    "80029564": ("NP Error",         "PlayStation Network error -> check internet connection"),
    "8002A537": ("NP Timeout",       "PSN connection timeout -> check NAT type & router"),
    "8002A548": ("NP Disconnected",  "PSN connection lost -> check internet connection"),
    "80022D11": ("BD Drive Error",   "Blu-ray drive internal error -> replace BD drive"),
    "80010017": ("Save Corrupt",     "Save data corrupt -> delete save data"),
    "8002B241": ("DRM Error",        "Content license issue -> restore licences in Account Mgmt"),
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
