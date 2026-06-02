# Flipdot display — diagnosis (2026-05-29 session)

## Symptom
The physical flipdot panel shows a **different random "cellular-automata-like"
scatter on every power-cycle, then stays frozen** — it does not respond to any
serial output from the Pi.

## Verdict: NOT a software problem (exhaustively ruled out)
Everything on the Pi/serial side is healthy. The bytes leave the Pi correctly;
the panel never reacts. The break is **physical / electrical between the FTDI's
TX and the panel controller's input, or the controller's serial receiver is not
processing data.**

### What was tested remotely (all produced ZERO dot movement)
- Native repo protocol (`0x81/0x82`, 150-byte fill) — pyserial **and** RawSerial
- AlfaZeta framing (`0x80 … 0x8F`) — every address / width / baud, incl. load+refresh
- Hanover framing (STX/ETX/checksum) — every address / width / baud
- All 6 baud rates (4800–115200)
- Every static DTR/RTS combination + a DTR reset pulse
- RS-485 driver-enable emulation (RTS & DTR, both polarities)
- **The original proven `simple_working_double_height.py` + pyserial core** that
  used to drive this panel — also nothing

### What was PROVEN healthy
- FTDI physically transmits: `tcdrain` timing matches the baud rate exactly
  (2400 B @ 4800 = 5.000 s, 9600 B @ 38400 = 2.500 s).
- FTDI adapter is `A3000lDq` (same serial as the old Mac setup), direct to the
  Pi (behind the Pi's internal VL805 hub — normal), driver `ftdi_sio` bound.
- No serial-port contention — the Flask app was stopped for all protocol tests;
  only one process ever held `/dev/ttyUSB0` at a time.

## The "random pattern per boot" clue
Interpreted as the controller dumping **uninitialized framebuffer RAM** to the
dots at power-on (random, differs each boot), then freezing because it never
receives valid serial frames to overwrite it. The dot-driving works; the serial
intake does not.

## NEXT STEP — power-cycle test (must be on-site)
Run `hardware/probes/morning_powercycle_test.py` (streams all-ON continuously),
power-cycle the panel during it, and observe the boot state:
- **Solid all-ON** → data reaches the controller; protocol fine; only the repo's
  RawSerial transport is at fault (revert `core/core.py` serial layer to pyserial).
- **Random scatter again** → data not reaching the controller → physical link.

## On-site checklist (fastest path)
1. Reseat the data wire **FTDI TX → panel data-in**; confirm a **common ground**
   between the Pi/FTDI and the panel.
2. **FTDI loopback**: jumper the adapter's TX→RX and run a read/write test to
   prove the adapter outputs on its pin; then check **continuity** from FTDI TX
   to the panel's data terminal. Isolates adapter vs. cable in ~2 min.
3. If the panel is **RS-485** (the `0x81/0x82` opcodes suggest an AlfaZeta-style
   controller), confirm there is a powered **TTL→RS-485 transceiver** in the line
   (bare FTDI TTL will not drive an RS-485 input). If so, the AlfaZeta framing in
   `hardware/probes/proto_probe.py` is the likely-correct protocol once the
   transceiver is in place.

## Side issue: webcam + mic not enumerating
Only the FTDI appears on the USB bus. The webcam (LifeCam) and Blue Yeti mic —
and the external hub they are on — do **not** enumerate (no `/dev/video*`, no USB
audio card, no external hub device in `lsusb -t`). Likely an unpowered/under-
powered hub or a dead upstream port. Fix on-site: powered hub + reseat the hub's
upstream cable into a known-good Pi USB port. (A working webcam would also enable
automated visual verification of display tests.)

## Software fix already made this session
`transition/transition.py`: a transition function named `random` shadowed
`import random`, crashing `matrix_effect` and any `random.choice` path
(`'function' object has no attribute 'choice'`). Aliased the import to `_random`.
Real bug, independent of the hardware. (Uncommitted as of this note.)

## Probe scripts (hardware/probes/)
- `morning_powercycle_test.py` — the on-site power-cycle test (start here)
- `hwtest.py` — fill board via RawSerial or pyserial (`hwtest.py raw|pyserial`)
- `baudsweep.py` — all-on flash across 6 baud rates
- `proto_probe.py` — AlfaZeta + Hanover protocol sweep
- `rs485_test.py` / `rs485_manual.py` — RS-485 driver-enable attempts
- `dtr_test.py` — DTR/RTS line-state sweep
- `direct_pi_test.py` / `slow_test.py` — minimal + camera-paced patterns
