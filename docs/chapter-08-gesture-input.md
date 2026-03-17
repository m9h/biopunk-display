# Chapter 8: Gesture Input via Leap Motion

## Minority Report, but for Real

The Leap Motion Controller is a small USB device that tracks hands and fingers
in 3D space with sub-millimeter accuracy. We use it to detect gestures —
swipes, circles, taps — and map them to display actions.

## No SDK Required

The Leap Motion service exposes a WebSocket on `localhost:6437` that streams
JSON frames at ~60fps. Each frame contains hand positions, finger data, and
recognized gestures. We just need `websocket-client` to connect:

```python
ws = websocket.create_connection('ws://localhost:6437/v6.json')
ws.send(json.dumps({'enableGestures': True}))

while True:
    frame = json.loads(ws.recv())
    gestures = frame.get('gestures', [])
```

This is much simpler than using the native C++ SDK, and it works on any platform
where the Leap Motion service runs.

## Gesture Mapping

| Gesture      | Direction | Display Action           |
|--------------|-----------|--------------------------|
| Swipe left   | ←         | "SWIPE LEFT" (righttoleft) |
| Swipe right  | →         | "SWIPE RIGHT" (slide_in)  |
| Swipe up     | ↑         | "HELLO!" (pop)            |
| Swipe down   | ↓         | Clear display             |
| Circle       | any       | "BIOPUNK" (dissolve)      |
| Key tap      | down      | "TAP" (typewriter)        |

The gesture direction is determined by the `direction` vector in the gesture data.
We compare the absolute X and Y components to determine horizontal vs. vertical:

```python
if abs(direction[0]) > abs(direction[1]):
    action = 'swipe_left' if direction[0] < 0 else 'swipe_right'
else:
    action = 'swipe_up' if direction[1] > 0 else 'swipe_down'
```

## Cooldown

Without a cooldown, a single hand wave could trigger dozens of gestures:

```python
if now - self._last_gesture_time < self._cooldown:
    return
```

The default 2-second cooldown ensures one gesture = one action. This is tunable
via `LEAP_COOLDOWN` in the config.

## Reconnection

The Leap Motion service might restart, or the USB device might be unplugged and
replugged. The listener handles this gracefully:

```python
while self._running:
    try:
        ws = websocket.create_connection(self._ws_url, timeout=5)
        while self._running:
            frame = json.loads(ws.recv())
            self._process_frame(frame)
    except Exception:
        time.sleep(5)  # retry after delay
```

## What's Next

Chapter 9 adds webcam presence detection — the display knows when someone is
standing in front of it and reacts accordingly.
