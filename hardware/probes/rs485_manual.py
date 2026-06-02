#!/usr/bin/env python3
"""Manual RS-485 driver-enable emulation: toggle RTS (and also try DTR) as the
transmit-enable around each frame, since the FTDI driver lacks kernel RS485.
Frame drains fully (flush) while DE is asserted, then DE is released."""
import time, serial

PORT = '/dev/ttyUSB0'

def alfazeta(data, addr=0x00, cmd=0x83):
    return bytes([0x80, cmd, addr]) + bytes(data) + bytes([0x8F])
def native(data30):
    return b'\x81\x82' + bytes(data30[:30]).ljust(30, b'\x00')

frames = [
    ("AlfaZeta on addr0x00", alfazeta([0xFF]*28), alfazeta([0x00]*28)),
    ("native on",            native([0x7f]*30),    native([0x00]*30)),
]

def send_de(ser, data, de_attr, de_tx, settle=0.001):
    setattr(ser, de_attr, de_tx)        # enable driver
    time.sleep(settle)
    ser.write(data); ser.flush()        # flush waits for full transmission
    time.sleep(settle)
    setattr(ser, de_attr, not de_tx)    # release driver

for de_attr in ('rts', 'dtr'):
    for de_tx in (True, False):
        for baud in (19200, 57600, 9600):
            print(f"\n##### DE={de_attr} tx_level={de_tx} @ {baud} #####")
            try:
                ser = serial.Serial(PORT, baud, timeout=1)
            except Exception as e:
                print("  open failed:", e); continue
            for label, on, off in frames:
                print(f"  -> {label} (watch ~2s)")
                for _ in range(2):
                    send_de(ser, on, de_attr, de_tx);  time.sleep(0.4)
                    send_de(ser, off, de_attr, de_tx); time.sleep(0.4)
            ser.close()

print("\n[rs485-manual] done — call out any label that flipped dots")
