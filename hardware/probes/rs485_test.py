#!/usr/bin/env python3
"""Try RS-485 driver-enable mode: RTS auto-toggles as transmit-enable during
each write. Commercial flipdot panels (AlfaZeta/Hanover) use RS-485, and a
TTL UART that never asserts the driver-enable line puts nothing on the bus.
Tries both RTS polarities, with both the native and AlfaZeta framing."""
import time, serial
import serial.rs485

PORT = '/dev/ttyUSB0'

def alfazeta(data, addr=0x00, cmd=0x83):
    return bytes([0x80, cmd, addr]) + bytes(data) + bytes([0x8F])

def native(data30):  # repo-style: 0x81 0x82 + 30 cols
    return b'\x81\x82' + bytes(data30[:30]).ljust(30, b'\x00')

frames = [
    ("AlfaZeta all-on  addr0x00", alfazeta([0xFF]*28), alfazeta([0x00]*28)),
    ("AlfaZeta all-on  addr0xFF", alfazeta([0xFF]*28, 0xFF), alfazeta([0x00]*28, 0xFF)),
    ("native 0x81/0x82 all-on",   native([0x7f]*30),       native([0x00]*30)),
]

for rts_for_tx in (True, False):
    for baud in (19200, 57600, 9600):
        print(f"\n##### RS485 rts_level_for_tx={rts_for_tx} @ {baud} #####")
        try:
            ser = serial.Serial(PORT, baud, timeout=1)
            ser.rs485_mode = serial.rs485.RS485Settings(
                rts_level_for_tx=rts_for_tx,
                rts_level_for_rx=not rts_for_tx,
                delay_before_tx=0.0,
                delay_before_rx=0.0,
            )
        except Exception as e:
            print("  setup failed:", repr(e));
            try: ser.close()
            except Exception: pass
            continue
        for label, on, off in frames:
            print(f"  -> {label} (watch ~2s)")
            for _ in range(2):
                ser.write(on);  ser.flush(); time.sleep(0.4)
                ser.write(off); ser.flush(); time.sleep(0.4)
        ser.close()

print("\n[rs485] done — call out any label that flipped dots")
