# Chapter 9: Webcam Presence Detection

## The Display That Sees You

A display that shows the same message to an empty room and a crowded one is
wasting energy. With a simple webcam (Microsoft LifeCam HD-3000) and OpenCV's
frame differencing, we give the display spatial awareness: it knows when
someone is there.

## No Machine Learning Required

We don't need face detection or person recognition. The question is simpler:
"Is something moving in front of the display?" Frame differencing answers this
with basic math.

### The Algorithm

1. Capture a frame, convert to grayscale, apply Gaussian blur
2. Compare with the previous frame using absolute difference
3. Threshold the difference image (ignore tiny changes from noise)
4. Sum the white pixels — that's your motion score

```python
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
gray = cv2.GaussianBlur(gray, (21, 21), 0)

delta = cv2.absdiff(prev_gray, gray)
thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
motion_score = thresh.sum() // 255
```

**Gaussian blur** smooths out sensor noise that would cause false positives.
The `(21, 21)` kernel is large enough to ignore pixel-level flicker while
preserving person-sized movement.

**Threshold of 25** means a pixel must change by at least 25/255 brightness
levels to count as motion. This filters out subtle lighting changes.

## State Machine

The webcam module tracks a simple two-state model:

```
[Absent] --motion_score > threshold--> [Present] → send greeting
[Present] --10 frames no motion-----> [Absent]  → send farewell
```

The 10-frame hysteresis prevents flickering — a momentary stillness (checking
your phone) doesn't trigger a goodbye.

### Cooldown

```python
if not self._present and (now - last_trigger) > self._cooldown:
    self._present = True
    self._trigger_greeting()
```

The 30-second cooldown prevents the display from greeting someone who just
stepped back and returned. Without it, walking to the coffee machine and back
would trigger two greetings.

## Priority

Presence greetings use **priority 3** — higher than playlists (0), gestures (1),
and even voice (2). The rationale: if someone just walked up to the display,
acknowledging their presence is more important than finishing a queued message.

## Resource Efficiency

The webcam check runs every 1 second (`WEBCAM_CHECK_INTERVAL`), not at 30fps.
For presence detection, we don't need smooth video — we need occasional snapshots.
This keeps CPU usage on the Pi minimal.

```python
while self._running:
    time.sleep(self._check_interval)
    ret, frame = cap.read()
    # ... process one frame
```

## Configuration

| Setting                    | Default | Description                    |
|----------------------------|---------|--------------------------------|
| `WEBCAM_DEVICE`            | 0       | `/dev/video0`                  |
| `WEBCAM_MOTION_THRESHOLD`  | 5000    | Pixel count to trigger presence |
| `WEBCAM_GREETING`          | WELCOME | Message shown on arrival       |
| `WEBCAM_FAREWELL`          | GOODBYE | Message shown on departure     |
| `WEBCAM_COOLDOWN`          | 30      | Seconds between greetings      |

## What's Next

Chapter 12 introduces playlists — JSON files that define sequences of messages
the display can loop through as ambient content.
