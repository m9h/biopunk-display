#!/usr/bin/env python3
"""MORNING POWER-CYCLE TEST  (run while you are physically at the display)

Purpose: determine whether the FTDI's serial data actually reaches the panel
controller, by streaming an unmistakable all-dots-ON frame continuously while
you power-cycle the panel.

HOW TO RUN (from the repo root, with the Flask app NOT running):
    .venv/bin/python hardware/probes/morning_powercycle_test.py

Then, while it is streaming:
    1. Power-cycle the panel (cut power, wait 3s, restore).
    2. Watch how the board comes up:
         * SOLID ALL-ON (every dot flipped on)  -> data IS reaching the
           controller. The protocol works; the only repo issue is the RawSerial
           transport (revert core/core.py serial layer to pyserial).
         * RANDOM scatter again                 -> data is NOT reaching the
           controller. Physical link problem: check the data wire FTDI TX ->
           panel data-in, common ground, and (if RS-485) the transceiver.

Uses the ORIGINAL proven pyserial core from the old working directory.
"""
import sys, time

# Use the original (pyserial) working core from the archived directory.
OLD = '/home/flipdots/.local/share/Trash/files/biohacker-flipdots'
sys.path.insert(0, OLD)
import core.core as cc   # auto-inits and opens /dev/ttyUSB0 via pyserial

ALL_ON = bytes([0x7f]) * 105
print("serial transport:", type(cc.ser_main).__name__)
print("Streaming ALL-ON continuously. Power-cycle the panel now.")
print("Ctrl-C to stop.")
try:
    while True:
        cc.working_core.fill(ALL_ON)
        time.sleep(0.25)
except KeyboardInterrupt:
    print("\nstopped")
