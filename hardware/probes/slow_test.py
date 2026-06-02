#!/usr/bin/env python3
"""Camera-friendly slow test: hold each pattern long enough for a Nest cam
(latency + low framerate) and the physical dots to settle. Top candidates only."""
import time, serial

PORT = '/dev/ttyUSB0'
HOLD = 12  # seconds per state

def native(data30):
    return b'\x81\x82' + bytes(data30[:30]).ljust(30, b'\x00')
def alfazeta(data, addr=0x00, cmd=0x83):
    return bytes([0x80, cmd, addr]) + bytes(data) + bytes([0x8F])

def hold(ser, frame, label):
    print(f"  >>> {label}  — HOLDING {HOLD}s — look now")
    t0 = time.time()
    # resend a few times across the hold so a late-watching camera still catches it
    while time.time() - t0 < HOLD:
        ser.write(frame); ser.flush()
        time.sleep(1.0)

tests = [
    ("NATIVE 38400", 38400, [
        (native([0x7f]*30), "NATIVE all dots ON"),
        (native([0x00]*30), "NATIVE all dots OFF"),
        (native([0x7f if i%2==0 else 0 for i in range(30)]), "NATIVE checkerboard"),
    ]),
    ("ALFAZETA 19200 addr0x00", 19200, [
        (alfazeta([0xFF]*28), "ALFAZETA all ON"),
        (alfazeta([0x00]*28), "ALFAZETA all OFF"),
    ]),
    ("ALFAZETA 57600 broadcast", 57600, [
        (alfazeta([0xFF]*28, 0xFF), "ALFAZETA broadcast all ON"),
        (alfazeta([0x00]*28, 0xFF), "ALFAZETA broadcast all OFF"),
    ]),
]

for name, baud, frames in tests:
    print(f"\n##### {name} #####")
    ser = serial.Serial(PORT, baud, timeout=1)
    for frame, label in frames:
        hold(ser, frame, label)
    ser.close()

print("\n[slow] done")
