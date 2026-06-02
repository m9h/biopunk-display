#!/usr/bin/env python3
"""FTDI loopback test — proves whether the adapter transmits & receives on its pins.

SETUP (on-site):
  Jumper the FTDI's  TX  pin directly to its  RX  pin.
  (Disconnect the panel lead first if needed.)

Then run:  .venv/bin/python hardware/probes/loopback_test.py

RESULT:
  * Bytes echoed back  -> the FTDI adapter works on its own pins. The fault is
    DOWNSTREAM: the wire from TX to the panel, the panel's RX, or a TTL-vs-RS485
    level mismatch.
  * Nothing echoed     -> the FTDI adapter (or its TX/RX pins) is the problem.
"""
import serial, time

ser = serial.Serial('/dev/ttyUSB0', 38400, timeout=1)
ser.reset_input_buffer()
probe = b'FLIPDOT-LOOPBACK-12345'
print("writing:", probe)
ser.write(probe); ser.flush()
time.sleep(0.3)
got = ser.read(len(probe))
ser.close()
print("read back:", got)
if got == probe:
    print("\n✅ LOOPBACK OK — adapter transmits & receives. Fault is DOWNSTREAM (wire/panel/levels).")
elif got:
    print(f"\n⚠️  PARTIAL echo ({len(got)}/{len(probe)} bytes) — flaky adapter or wiring.")
else:
    print("\n❌ NO echo — TX→RX jumper missing, or the adapter/pins are faulty.")
