#!/usr/bin/env python3
"""Minimal manual protocol probe on the Pi — replicates the proven direct_test.py
sequence (0x81 reset, 0x82 row-select, 30 data bytes) on /dev/ttyUSB0."""
import time, serial

ser = serial.Serial('/dev/ttyUSB0', 38400, timeout=1)
print("opened /dev/ttyUSB0 @ 38400 (pyserial)")

def row(data30):
    ser.write(b'\x81')          # RESET
    ser.write(b'\x82')          # ROW select
    ser.write(data30[:30].ljust(30, b'\x00'))
    ser.flush()

try:
    print("1. clear")
    row(b'\x00' * 30); time.sleep(1)

    print("2. ALL DOTS ON (30 cols) — watch the board")
    row(b'\x7f' * 30); time.sleep(3)

    print("3. alternating columns")
    row(bytes([0x7f if i % 2 == 0 else 0x00 for i in range(30)])); time.sleep(3)

    print("4. ALL ON again")
    row(b'\x7f' * 30); time.sleep(3)

    print("5. clear")
    row(b'\x00' * 30); time.sleep(1)
finally:
    ser.close()
    print("done")
