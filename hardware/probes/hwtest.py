#!/usr/bin/env python3
"""Direct hardware test — bypasses Flask. Drives the panel with a chosen serial driver."""
import sys, os, time

PORT = '/dev/ttyUSB0'
BAUD = 38400
TCOLUMN = 105
reset = bytes([0x81])   # row1 control byte used by core (reset + row1)
row1  = bytes([0x82])
# We import the real framing from core to stay faithful to the protocol.
import core.core as cc

def make_open(kind):
    if kind == 'raw':
        return cc.RawSerial(PORT, BAUD)
    elif kind == 'pyserial':
        import serial
        return serial.Serial(PORT, BAUD, timeout=1)
    raise SystemExit('kind must be raw|pyserial')

kind = sys.argv[1] if len(sys.argv) > 1 else 'raw'
print(f"[hwtest] opening {PORT} @ {BAUD} via {kind}")
ser = make_open(kind)
cc.ser_main = ser            # core.fill() writes through this global
core = cc.WorkingFlipdotCore.__new__(cc.WorkingFlipdotCore)  # skip __init__ (don't reopen)

print("[hwtest] ALL DOTS ON (whole board should flip black->yellow)")
core.fill(bytes([0x7f]) * TCOLUMN)   # 0x7f = all 7 rows set
time.sleep(2.5)
print("[hwtest] ALL DOTS OFF")
core.fill(bytes([0x00]) * TCOLUMN)
time.sleep(1.5)
print("[hwtest] checkerboard")
core.fill(bytes([0x55 if i % 2 == 0 else 0x2a for i in range(TCOLUMN)]))
time.sleep(2.5)
print("[hwtest] clear")
core.fill(bytes([0x00]) * TCOLUMN)
try:
    ser.close()
except Exception:
    pass
print("[hwtest] done")
