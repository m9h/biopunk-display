#!/usr/bin/env python3
"""Baud sweep using the minimal row protocol (0x81 0x82 + 30 bytes).
Flashes the whole visible row ON/OFF at each baud. Watch for ANY dot movement."""
import time, serial

PORT = '/dev/ttyUSB0'
BAUDS = [4800, 9600, 19200, 38400, 57600, 115200]

def row(ser, data30):
    ser.write(b'\x81'); ser.write(b'\x82')
    ser.write(data30[:30].ljust(30, b'\x00'))
    ser.flush()

for baud in BAUDS:
    print(f"\n=== BAUD {baud} === (watch ~4s)")
    try:
        ser = serial.Serial(PORT, baud, timeout=1)
    except Exception as e:
        print(f"  open failed: {e}"); continue
    for _ in range(4):
        row(ser, b'\x7f' * 30); time.sleep(0.4)
        row(ser, b'\x00' * 30); time.sleep(0.4)
    ser.close()
    time.sleep(0.4)

print("\n[sweep] done — which baud (if any) flipped dots?")
