#!/usr/bin/env python3
"""Try real flipdot controller protocols against the panel.
Primary hypothesis: AlfaZeta (the repo's 0x81/0x82 are AlfaZeta opcodes used
without the required 0x80...0x8F framing). Also tries Hanover as a fallback.
Watch the board for ANY dots flipping; note the label when they do."""
import time, serial

PORT = '/dev/ttyUSB0'

def alfazeta_frame(data, address=0x00, cmd=0x83):
    # 0x80 START, cmd, address, data..., 0x8F END
    return bytes([0x80, cmd, address]) + bytes(data) + bytes([0x8F])

def hanover_frame(data, address=0):
    p = b'\x02' + b'1' + format(address, 'X').encode() + format(len(data), '02X').encode()
    for b in data:
        p += format(b, '02X').encode()
    p += b'\x03'
    s = sum(p[1:]) & 0xFF
    crc = ((s ^ 0xFF) + 1) & 0xFF
    p += format(crc, '02X').encode()
    return p

def flash(ser, frame_on, frame_off, n=3, dt=0.45):
    for _ in range(n):
        ser.write(frame_on);  ser.flush(); time.sleep(dt)
        if frame_off is not None:
            ser.write(frame_off); ser.flush(); time.sleep(dt)

# ---- AlfaZeta sweep: addresses x widths x bauds x cmd ----
ALFA_BAUDS = [57600, 19200, 9600, 115200]
ALFA_ADDRS = [0x00, 0x01, 0xFF]          # 0xFF = broadcast on many panels
ALFA_WIDTHS = [28, 30]                    # common panel column counts
ALFA_FILL = 0xFF                          # all dots on (8 rows); 0x7F for 7 rows

for baud in ALFA_BAUDS:
    print(f"\n##### AlfaZeta @ {baud} baud #####")
    try:
        ser = serial.Serial(PORT, baud, timeout=1)
    except Exception as e:
        print("  open failed:", e); continue
    for addr in ALFA_ADDRS:
        for width in ALFA_WIDTHS:
            for fill in (0xFF, 0x7F):
                label = f"AlfaZeta cmd=0x83 addr=0x{addr:02X} width={width} fill=0x{fill:02X}"
                print(f"  -> {label}  (watch ~2.5s)")
                on  = alfazeta_frame([fill]*width, address=addr, cmd=0x83)
                off = alfazeta_frame([0x00]*width, address=addr, cmd=0x83)
                flash(ser, on, off, n=2, dt=0.4)
    # also try load(0x82)+refresh(0x81) two-step on addr 0
    print("  -> AlfaZeta load(0x82)+refresh(0x81) addr=0x00 width=28")
    for _ in range(2):
        ser.write(alfazeta_frame([0xFF]*28, 0x00, 0x82)); ser.flush()
        ser.write(bytes([0x80, 0x81, 0x8F])); ser.flush(); time.sleep(0.5)
        ser.write(alfazeta_frame([0x00]*28, 0x00, 0x82)); ser.flush()
        ser.write(bytes([0x80, 0x81, 0x8F])); ser.flush(); time.sleep(0.4)
    ser.close()

# ---- Hanover fallback ----
for baud in [4800, 9600, 19200]:
    print(f"\n##### Hanover @ {baud} baud #####")
    try:
        ser = serial.Serial(PORT, baud, timeout=1)
    except Exception as e:
        print("  open failed:", e); continue
    for addr in (0, 1):
        for width in (28, 30, 16):
            print(f"  -> Hanover addr={addr} width={width}  (watch ~2s)")
            on  = hanover_frame([0xFF]*width, address=addr)
            off = hanover_frame([0x00]*width, address=addr)
            flash(ser, on, off, n=2, dt=0.4)
    ser.close()

print("\n[probe] done — call out the label of ANY frame that flipped dots")
