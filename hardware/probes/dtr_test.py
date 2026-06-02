#!/usr/bin/env python3
"""Sweep DTR/RTS line states (the classic Mac->Linux FTDI gap) while sending
the all-dots-on row. Watch the board for ANY flip on any combination."""
import time, serial

PORT, BAUD = '/dev/ttyUSB0', 38400
ALL_ON  = b'\x81\x82' + b'\x7f' * 30
ALL_OFF = b'\x81\x82' + b'\x00' * 30

def send(ser, data):
    ser.write(data); ser.flush()

combos = [
    ('dtr=0 rts=0', False, False),
    ('dtr=1 rts=1', True,  True),
    ('dtr=0 rts=1', False, True),
    ('dtr=1 rts=0', True,  False),
]
for label, dtr, rts in combos:
    print(f"\n=== {label} === watch ~3s")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    try:
        ser.dtr = dtr; ser.rts = rts
    except Exception as e:
        print(f"  (line set raised {e!r} — continuing)")
    time.sleep(0.2)
    for _ in range(3):
        send(ser, ALL_ON);  time.sleep(0.4)
        send(ser, ALL_OFF); time.sleep(0.4)
    ser.close()

# DTR reset pulse then send
print("\n=== DTR pulse (toggle) then all-on === watch ~3s")
ser = serial.Serial(PORT, BAUD, timeout=1)
try:
    ser.dtr = True;  time.sleep(0.1)
    ser.dtr = False; time.sleep(0.1)
    ser.dtr = True;  time.sleep(0.2)
except Exception as e:
    print(f"  (pulse raised {e!r})")
for _ in range(3):
    send(ser, ALL_ON);  time.sleep(0.5)
    send(ser, ALL_OFF); time.sleep(0.3)
ser.close()
print("\ndone")
