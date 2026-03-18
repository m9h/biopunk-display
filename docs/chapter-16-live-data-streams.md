# Chapter 16: Live Data Streams

## A Window Into the Living World

In every chapter before this one, the display showed what we told it. A user typed
a message, a voice command spoke a phrase, a cellular automaton computed its next
generation -- and the display rendered the result. The display was a terminal: it
received instructions and executed them.

This chapter inverts that relationship. The display starts *listening to the
world* and reporting what it hears. It polls a weather API and clicks out the
temperature. It reads `/proc/meminfo` and shows how hard the Pi is working. It
tracks the International Space Station and, when the ISS passes overhead, flips
every dot to shout `ISS OVERHEAD NOW! LOOK UP!`.

This is a fundamental architectural shift. The display stops being an output device
and becomes a **sensor frontend** -- a physical surface that makes invisible data
streams visible. Weather, system health, orbital mechanics, lab conditions -- each
becomes a pattern of electromagnetic dots clicking into position.

For the ALife/GECCO audience: this is the display's transition from a closed system
to an open one. Chapters 1-15 built a self-contained universe -- messages in, dots
out. This chapter connects the display to the environment. In artificial life terms,
we are giving the system *perception*. And once a system perceives, it behaves
differently.

## From Notification to Ambient Information

Before we write code, we need to think about what kind of information display we
are building. There are two fundamentally different paradigms:

**Notification displays** demand attention. Your phone buzzes. A desktop
notification slides in. A car dashboard lights up a warning icon. The design
intent is *interrupt* -- stop what you are doing and attend to this.

**Ambient displays** reward attention without demanding it. A clock on the wall
does not buzz when the minute changes. A weather vane does not send you a push
notification when the wind shifts. They are *there*, always current, always
available, never insistent.

The flipdot display is almost uniquely suited to ambient information. It has no
backlight, no glow, no pixel refresh -- a message rendered on flipdots stays
rendered with zero power consumption, silently waiting for someone to glance at it.
The only moment it demands attention is the click of dots flipping, and that sound
fades in seconds. After that, it is a matte black-and-yellow panel showing
information that is simply *present* in the room.

This means our data streams should be designed for peripheral awareness:

- **Brevity.** The visible area is 30 columns of 7 rows. A text message scrolls
  through, but the ambient "glance value" comes from what fits in 30 characters.
  `18C PARTLY CLOUDY WIND 12KPH` works. A five-sentence weather report does not.
- **Cadence.** A stream that updates every second is not ambient; it is a
  distraction. One that updates every five minutes blends into the environment.
  The update rate should match the information's natural rate of change.
- **Graceful absence.** When a data source is unavailable (network down, API
  error, sensor disconnected), the display should not show an error dialog. It
  should show *nothing from that source*, or a single understated fallback, and
  carry on with whatever else it has.

These are not just UX preferences. They are the design principles of **calm
technology**, a concept developed by Mark Weiser and John Seely Brown at Xerox
PARC in 1995. Their insight -- that the most profound technologies are those that
disappear into the fabric of everyday life -- maps perfectly onto a flipdot display
mounted on a lab wall.

## The Plugin Architecture

### The Strategy Pattern, Again

In Chapter 15, we built a generator engine where each cellular automaton was a
class with `reset()` and `tick()` methods. The engine did not know or care which
rule it was running. We noted that this was the Strategy pattern.

The stream engine uses the same architecture with a different interface. Each data
source is a class with a `fetch()` method:

```python
class MySource:
    name = 'my_source'
    description = 'What this source shows'
    interval = 60  # seconds between fetches

    def fetch(self):
        return {
            'text': 'THE DATA',
            'transition': 'righttoleft',
            'priority': 0,
        }
```

Four attributes, one method. That is the entire contract:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `name` | `str` | Unique identifier, used in API URLs and thread names |
| `description` | `str` | Human-readable explanation for the `/api/streams` listing |
| `interval` | `int` | Seconds between fetches -- the source's natural cadence |
| `fetch()` | method | Returns a dict with `text`, `transition`, and optionally `priority` and `bar_value` |

The engine handles everything else: threading, scheduling, error handling, queue
integration, and lifecycle management. You write `fetch()`. The engine does the
rest.

This separation is not just good software design -- it is a deliberate editorial
choice about where complexity should live. A data source author should think about
*what to display*, not about threads or database sessions or byte buffers. The
engine absorbs that complexity so the source stays focused.

### Why `fetch()` Returns a Dict

The return value of `fetch()` is a plain dictionary, not a custom class or a
protocol buffer or a typed dataclass. This is deliberate:

```python
{
    'text': 'CPU 52C | LOAD 0.43 | MEM 67%',  # What to show (required)
    'transition': 'righttoleft',                 # How to show it (optional, default: righttoleft)
    'priority': 0,                               # Queue priority (optional, default: 0)
    'bar_value': None,                           # 0-7 for bar graph mode (optional)
    'label': '',                                 # Label for bar graph (optional)
}
```

A dict is the simplest possible data contract. It serializes naturally to JSON
(for the API), it is trivially inspectable in a debugger, and it does not require
source authors to import anything. When you prototype a new data source, you can
start by returning `{'text': 'hello'}` and iterate from there.

The `priority` field is what connects streams to the rest of the system. Streams
default to priority 0 -- the lowest -- which means they yield to everything:
voice commands (typically priority 3), presence greetings (priority 2), and
workshop submissions (priority 1). But a stream *can* elevate its priority for
alerts. When the ISS tracker detects an overhead pass, it returns priority 5 --
higher than everything except emergency messages. The priority queue handles the
rest.

## The Stream Engine

The `StreamEngine` class in `app/streams/engine.py` is the orchestrator. Let us
walk through it piece by piece.

### Initialization and Registration

```python
class StreamEngine:
    def __init__(self, app=None):
        self._app = None
        self._sources = {}
        self._active = {}        # name -> thread
        self._running_flags = {} # name -> bool
        if app is not None:
            self.init_app(app)
```

The engine maintains three dictionaries:

- **`_sources`** maps source names to source objects. This is the registry of
  *available* data sources -- everything the system knows how to do.
- **`_active`** maps source names to running `threading.Thread` objects. This is
  what is *currently running*.
- **`_running_flags`** maps source names to booleans. This is how we signal
  threads to stop.

The two-dictionary design (active threads vs. running flags) is a common pattern
for cooperative thread cancellation in Python. We cannot forcibly kill a thread
(Python does not support that safely), so instead we set a flag and the thread
checks it periodically.

### App Integration

```python
def init_app(self, app):
    self._app = app

    # Register built-in sources
    from app.streams.sources import (
        SystemStats, ClockStream, CountdownStream, SensorSimulator
    )
    self.register(SystemStats())
    self.register(ClockStream())
    self.register(CountdownStream())
    self.register(SensorSimulator())

    # Optional sources that need network
    try:
        from app.streams.sources import WeatherStream, ISSTracker
        self.register(WeatherStream())
        self.register(ISSTracker())
    except Exception:
        pass

    app.streams = self
```

Notice the two-tier registration. The first four sources (SystemStats, Clock,
Countdown, SensorSimulator) are registered unconditionally -- they have no
external dependencies and work on any system, even without a network connection.

The second tier (Weather, ISS Tracker) is wrapped in a try/except. These sources
use `urllib.request` to fetch data from the internet. On a system with no network
(a demo Pi at a conference, a lab behind a firewall), the import might succeed but
the first `fetch()` will fail -- and that is fine, because the engine handles
fetch errors gracefully (more on this below).

This two-tier approach is a form of **graceful degradation**: the system works with
whatever is available, rather than failing entirely because one optional component
is missing. This matters in the real world, where your Pi might boot before the
WiFi connects, or the ISS API might be down for maintenance.

### The Stream Loop

The heart of the engine is `_stream_loop`, the function that runs in each stream's
background thread:

```python
def _stream_loop(self, source):
    """Fetch data and send to display on interval."""
    while self._running_flags.get(source.name, False):
        try:
            result = source.fetch()
            if result and result.get('text'):
                self._send(result)
            elif result and result.get('bar_value') is not None:
                self._render_bar(result)
        except Exception as e:
            print(f'[stream:{source.name}] Error: {e}', file=sys.stderr)

        # Interruptible sleep
        for _ in range(source.interval * 10):
            if not self._running_flags.get(source.name, False):
                return
            time.sleep(0.1)
```

There are several design decisions worth studying here:

**1. The bare `except Exception`.** In most Python code, catching all exceptions
is considered bad practice. Here, it is essential. A data source fetches data from
the outside world -- a world that produces `ConnectionResetError`,
`json.JSONDecodeError`, `TimeoutError`, `KeyError` on malformed API responses, and
any number of unexpected failures. If the engine let *any* exception propagate,
the thread would die and the stream would silently stop running. The bare except
keeps the thread alive. The error is logged to stderr (where systemd's journal
captures it), and the loop continues. The next fetch might succeed.

This is the **let it crash, but keep the loop** pattern. Individual fetches can
fail. The stream persists.

**2. Interruptible sleep.** The naive approach would be `time.sleep(source.interval)`.
But if the interval is 300 seconds (the weather stream) and you call `stop_stream`,
you would wait up to 5 minutes for the thread to notice. Instead, the engine
sleeps in 0.1-second increments, checking the running flag each time. This means
`stop_stream` takes at most 100 milliseconds to take effect, regardless of the
source's interval.

The cost is trivial -- checking a dictionary lookup and sleeping for 100ms in a
loop uses essentially zero CPU. But the benefit is enormous for user experience:
streams start and stop responsively.

**3. Two output paths.** The engine checks for `text` first, then `bar_value`.
Text messages flow through the message queue (the same queue used by web forms,
voice input, and every other input). Bar-value results render a simple vertical bar
graph directly to the display buffer. This dual path lets sources choose their
rendering mode -- most use text, but a real-time sensor reading is more legible as
a visual bar than as scrolling characters.

### Feeding the Queue

When a stream produces text, the engine calls `_send`:

```python
def _send(self, result):
    text = result['text']
    transition = result.get('transition', 'righttoleft')
    priority = result.get('priority', 0)

    with self._app.app_context():
        from app.models import Message
        from app import db

        msg = Message(body=text, transition=transition,
                      source='stream', priority=priority)
        db.session.add(msg)
        db.session.commit()

        self._app.message_queue.enqueue(
            msg.body, msg.transition, msg.priority, msg.id
        )
```

Three things happen:

1. A `Message` row is written to SQLite with `source='stream'`. This gives us an
   audit trail -- every piece of data ever shown on the display is in the database,
   queryable, timestamped.
2. The message is enqueued in the priority queue with whatever priority the source
   specified.
3. The queue's background worker will dequeue it (in priority order) and call
   `DisplayManager.send_message()`, which renders it to the physical flipdots.

This means stream data flows through the exact same pipeline as everything else:

```
Data Source -> fetch() -> _send() -> SQLite + Priority Queue -> Display
```

There is no special rendering path for streams. A weather update competes for
display time with a voice command or a web form submission, and the priority queue
resolves conflicts. This is a consequence of the architectural decision made in
Chapter 5: *all roads lead to the queue.*

## The Built-in Data Sources

### System Stats

```
CPU 52C | LOAD 0.43 | MEM 67% | UP 148H
```

`SystemStats` is the most infrastructure-aware of our data sources. It reads
directly from the Linux virtual filesystem -- no external dependencies, no network
access, no pip packages. Just file I/O to pseudo-files that the kernel maintains:

```python
# CPU temperature
with open('/sys/class/thermal/thermal_zone0/temp') as f:
    temp_c = int(f.read().strip()) / 1000

# Load average
with open('/proc/loadavg') as f:
    load = f.read().split()[0]

# Memory usage
with open('/proc/meminfo') as f:
    lines = f.readlines()
    total = int(lines[0].split()[1])
    available = int(lines[2].split()[1])
    used_pct = int((1 - available / total) * 100)

# Uptime
with open('/proc/uptime') as f:
    uptime_sec = float(f.read().split()[0])
    hours = int(uptime_sec // 3600)
```

Each read is wrapped in its own try/except. If the thermal zone file does not
exist (some SBCs expose temperature differently), the temperature is simply
omitted from the output. The other fields still appear. This per-field resilience
is worth noting: the source does not produce all-or-nothing output. It produces
the best output it can given what the system provides.

**Why this matters on a Raspberry Pi.** The Pi 4 throttles its CPU when the
temperature exceeds 80C. If you are running cellular automata (which exercise the
CPU with tight numerical loops) plus data streams (which add periodic network I/O),
temperature monitoring is not academic -- it tells you whether your system is
approaching the thermal wall. Seeing `CPU 78C` on the display while running
reaction-diffusion is a signal to check your heatsink situation.

The 60-second interval is chosen to match the information's natural rate of change.
CPU temperature shifts over minutes, not seconds. Load average (the 1-minute value)
is already smoothed over 60 seconds by the kernel. Updating faster would produce
jittery readings without adding information.

The output format -- pipe-separated key-value pairs, all caps -- is designed for
the flipdot's 5x7 character set, which has no lowercase letters. The format
squeezes four data points into ~35 characters, which scrolls across the 30-column
display in about 4 seconds with the `righttoleft` transition. Glanceable.

### Clock

```python
class ClockStream:
    name = 'clock'
    description = 'Current time display (updates every 30s)'
    interval = 30

    def fetch(self):
        t = time.localtime()
        text = time.strftime('%H:%M', t)
        return {'text': text, 'transition': 'double_static'}
```

The simplest stream -- five characters, updated every 30 seconds. It uses the
`double_static` transition, which renders text using the double-height font and
holds it on the display (no scrolling). The result is a large, clear time
readout.

When your flipdot display is mounted on a wall, this becomes the most
satisfying clock in the building. The dots click to update the minute. The rest
of the time, it sits there silently, showing the time with no power draw (the
dots hold their state electromagnetically). Visitors invariably ask about it.

The 30-second interval means the displayed time can be up to 30 seconds stale.
For a wall clock, this is fine -- more accurate than most analog clocks, and far
more character. A shorter interval would cause more frequent flipping, which might
be distracting in a quiet office.

### Countdown Timer

```python
class CountdownStream:
    name = 'countdown'
    description = 'Countdown to a target time'
    interval = 10

    def __init__(self, target_epoch=None):
        self._target = target_epoch or (time.time() + 3600)

    def set_target(self, epoch):
        self._target = epoch

    def fetch(self):
        remaining = self._target - time.time()
        if remaining <= 0:
            return {'text': 'TIME IS UP!', 'transition': 'double_flash', 'priority': 5}

        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)

        if hours > 0:
            text = f'{hours}H {minutes:02d}M'
        elif minutes > 0:
            text = f'{minutes}M {seconds:02d}S'
        else:
            text = f'{seconds}S'

        return {'text': text, 'transition': 'plain'}
```

The countdown is the most stateful built-in source. It stores a `_target` epoch
and computes the remaining time on each fetch. The 10-second interval is shorter
than other sources because a countdown has urgency -- you want to see it ticking
down visibly.

The adaptive formatting (hours+minutes when far away, minutes+seconds when closer,
seconds alone in the final minute) ensures the display always shows the most
relevant granularity. And when time expires, two things change simultaneously:

1. The text switches to `TIME IS UP!`
2. The priority jumps from 0 to 5

That priority escalation is the key mechanism. During the countdown, the timer is
ambient -- priority 0, politely interleaving with other streams. The instant it
expires, it becomes the most urgent thing in the queue, jumping ahead of weather
updates, system stats, and workshop submissions. The `double_flash` transition
makes the display blink, which is the flipdot equivalent of a notification bell.

This is essential for workshops and presentations: "15 minutes left!" scrolling
past during a demo is ambient. "TIME IS UP!" flashing on the display while the
room clicks audibly -- that gets attention.

### Sensor Simulator

```python
class SensorSimulator:
    name = 'sensor_sim'
    description = 'Simulated lab sensor data (for demos)'
    interval = 15

    def __init__(self):
        self._t = 0
        self._sensors = [
            ('TEMP', 22, 3, 'C', 0.05),
            ('HUMID', 45, 10, '%', 0.03),
            ('CO2', 420, 50, 'PPM', 0.02),
            ('LIGHT', 500, 200, 'LUX', 0.07),
        ]

    def fetch(self):
        self._t += 1
        idx = self._t % len(self._sensors)
        name, base, amp, unit, freq = self._sensors[idx]

        value = base + amp * math.sin(self._t * freq) + random.gauss(0, amp * 0.1)
        text = f'{name}: {value:.1f} {unit}'

        return {'text': text, 'transition': 'typewriter'}
```

The sensor simulator generates realistic-looking environmental data using
sine waves with Gaussian noise. Each fetch cycles to the next sensor in the list,
so you see temperature, then humidity, then CO2, then light, repeating.

The data is fake, but the *shape* is realistic. Real environmental sensors produce
values that drift slowly (the sine component, with frequencies 0.02-0.07 so the
period is 90-315 ticks, or 22-79 minutes) with measurement noise on top (the
Gaussian term, scaled to 10% of the amplitude). The result looks convincing on a
display -- slowly varying readings that jitter slightly, exactly like a real
thermocouple or humidity sensor.

The purpose is twofold:

1. **Development and demos.** When you are working on the stream system at your
   desk (not near the Pi with real sensors), you need data to test with. The
   simulator provides it without any hardware.
2. **Template for real sources.** The simulator's interface is identical to what a
   real I2C temperature sensor or MQTT subscriber would implement. Replace the sine
   wave with `smbus2.read_byte_data(0x48, 0x00)` and you have a real sensor stream.
   The engine does not know the difference.

The 15-second interval and `typewriter` transition give sensor data a distinctive
feel -- frequent updates that spell out character by character, as if the
instrument is reporting.

### Weather (Open-Meteo)

```
18C PARTLY CLOUDY WIND 12KPH
```

The weather stream is the first source that reaches outside the Pi. It calls
the Open-Meteo API, a free and open-source weather data service that -- and
this is important for educational projects and conference demos -- **requires
no API key**. No signup, no rate limit registration, no environment variables to
configure. Just make an HTTP request and get weather data back.

```python
class WeatherStream:
    name = 'weather'
    description = 'Local weather from Open-Meteo (no API key needed)'
    interval = 300  # every 5 minutes

    def __init__(self, lat=42.36, lon=-71.09):
        self._lat = lat
        self._lon = lon

    def fetch(self):
        import urllib.request
        import json

        url = (
            f'https://api.open-meteo.com/v1/forecast'
            f'?latitude={self._lat}&longitude={self._lon}'
            f'&current_weather=true'
        )

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            weather = data['current_weather']
            temp = weather['temperature']
            wind = weather['windspeed']

            code = weather.get('weathercode', 0)
            conditions = {
                0: 'CLEAR', 1: 'MOSTLY CLEAR', 2: 'PARTLY CLOUDY',
                3: 'OVERCAST', 45: 'FOG', 48: 'RIME FOG',
                51: 'DRIZZLE', 53: 'DRIZZLE', 55: 'HEAVY DRIZZLE',
                61: 'RAIN', 63: 'RAIN', 65: 'HEAVY RAIN',
                71: 'SNOW', 73: 'SNOW', 75: 'HEAVY SNOW',
                80: 'SHOWERS', 81: 'SHOWERS', 82: 'HEAVY SHOWERS',
                95: 'THUNDERSTORM', 96: 'HAIL STORM', 99: 'HAIL STORM',
            }
            cond = conditions.get(code, f'WMO {code}')

            text = f'{temp:.0f}C {cond} WIND {wind:.0f}KPH'
            return {'text': text, 'transition': 'righttoleft'}

        except Exception as e:
            return {'text': f'WEATHER: {e}', 'transition': 'plain'}
```

Several things to notice:

**The WMO weather code mapping.** Open-Meteo returns integer weather codes
from the World Meteorological Organization standard. Code 0 is clear sky. Code
95 is thunderstorm. The mapping dictionary translates these to short uppercase
strings that fit the flipdot aesthetic. Some codes map to the same text (51, 53
are both `DRIZZLE`) because the fine-grained distinction (light vs. moderate)
is not meaningful on a 30-character display.

**The 300-second interval.** Weather does not change in seconds. Polling every
5 minutes is respectful to the API (Open-Meteo asks for reasonable usage), gives
the display time to show other streams between updates, and matches the natural
cadence of weather awareness. You check the weather a few times an hour, not a few
times a minute.

**The imports inside `fetch()`.** Notice that `urllib.request` and `json` are
imported inside the method, not at the top of the file. This is intentional: it
means the module can be *imported* on systems without network libraries (or where
import itself is slow on first load), and the cost of import is paid only when the
source actually runs. This is a micro-optimization that matters on a Pi where
startup time affects the user experience.

**The fallback on error.** If the API call fails (network down, timeout, malformed
response), the source returns `{'text': f'WEATHER: {e}', 'transition': 'plain'}`.
This is a design choice worth discussing. The alternative would be to return
`None` (which the engine treats as "nothing to display"). Showing the error is
more transparent -- you see `WEATHER: timed out` on the display and know
immediately that the network is down. In a production installation, you might
prefer the silent `None` approach. For development and debugging, the visible
error is invaluable.

**The default coordinates.** The default location is 42.36N, -71.09W -- Cambridge,
Massachusetts, near the MIT Media Lab. Change these to your lab's coordinates.
A future enhancement could read the location from Flask's config or auto-detect
it from the system's IP geolocation.

### ISS Tracker

```
ISS: 42.3N -71.1W
```

The ISS tracker is the most evocative of the built-in sources. It polls the
Open Notify API for the International Space Station's current position (latitude
and longitude, updated in real-time from NORAD orbital data) and shows it on the
display.

```python
class ISSTracker:
    name = 'iss_tracker'
    description = 'ISS position -- alerts when overhead'
    interval = 30

    def __init__(self, lat=42.36, lon=-71.09):
        self._lat = lat
        self._lon = lon

    def fetch(self):
        import urllib.request
        import json

        url = 'http://api.open-notify.org/iss-now.json'

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            pos = data['iss_position']
            iss_lat = float(pos['latitude'])
            iss_lon = float(pos['longitude'])

            dlat = abs(iss_lat - self._lat)
            dlon = abs(iss_lon - self._lon)
            nearby = dlat < 5 and dlon < 5

            if nearby:
                return {
                    'text': 'ISS OVERHEAD NOW! LOOK UP!',
                    'transition': 'double_flash',
                    'priority': 5,
                }
            else:
                text = f'ISS: {iss_lat:.1f}N {iss_lon:.1f}W'
                return {'text': text, 'transition': 'righttoleft'}

        except Exception:
            return None
```

The logic has two modes: ambient and alert.

**Ambient mode** (most of the time): the ISS is somewhere over the planet, and the
display shows its coordinates scrolling by. This is mildly interesting -- you see
the station moving across the globe, ticking through latitudes and longitudes as it
completes an orbit every 92 minutes. The 30-second interval means you see about
180 position updates per orbit, enough to sense the station's trajectory.

**Alert mode** (rare): the ISS passes within 5 degrees of latitude and 5 degrees
of longitude of your configured location. The display switches to
`ISS OVERHEAD NOW! LOOK UP!` with the `double_flash` transition and priority 5.
This jumps the queue, interrupts whatever else is playing, and produces the most
dramatic display effect available -- large text, flashing.

The proximity check uses a simple bounding-box comparison (`dlat < 5 and dlon < 5`),
not a great-circle distance. This is intentionally approximate. At mid-latitudes,
5 degrees of latitude is about 555 km and 5 degrees of longitude is about 370 km.
The ISS is visible from roughly 650 km away (depending on altitude and atmospheric
conditions), so the bounding box is a reasonable first approximation. A production
system might use the Haversine formula, but the bounding box has the virtue of
being obvious in the code -- no trigonometry to puzzle over.

**The `None` return on error.** Unlike the weather source, the ISS tracker returns
`None` when the API call fails. The engine checks for this and displays nothing.
This is the right choice here: the ISS position is interesting but not critical.
If the API is down, we would rather show nothing than clutter the display with
error text. The weather source shows errors because a weather outage is
operationally relevant (it probably means your network is down). An ISS API
outage is just a temporary inconvenience.

**Science outreach.** This is, frankly, the source that impresses visitors most.
A physical display on a wall, made of electromagnetic dots, that knows where the
International Space Station is -- and tells you when to look at the sky. It
transforms an abstract fact (there are humans orbiting Earth right now) into a
physical prompt (look up, you might see them). If you are using this display at a
conference booth or a university open house, start the ISS tracker.

## Error Handling and Graceful Degradation

The stream system is designed around the assumption that *things will fail*. APIs
go down. Networks drop. Sensors disconnect. The Pi overheats and throttles. The
question is not whether failures happen, but what the system does when they do.

The answer is layered:

### Layer 1: Per-Field Resilience (within a source)

The SystemStats source wraps each individual read in its own try/except:

```python
parts = []

try:
    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        temp_c = int(f.read().strip()) / 1000
        parts.append(f'CPU {temp_c:.0f}C')
except (FileNotFoundError, ValueError):
    pass

# ... same pattern for load, memory, uptime

text = ' | '.join(parts) if parts else f'{platform.node()} OK'
```

If the thermal zone file is missing, the temperature is omitted, but load, memory,
and uptime still appear. If *all* reads fail (running on macOS during development,
for instance), the fallback is the hostname with `OK` -- a minimal heartbeat that
tells you the stream is running even when it cannot read Linux-specific data.

### Layer 2: Per-Fetch Resilience (within the engine)

The stream loop catches all exceptions from `fetch()`:

```python
try:
    result = source.fetch()
    if result and result.get('text'):
        self._send(result)
except Exception as e:
    print(f'[stream:{source.name}] Error: {e}', file=sys.stderr)
```

A source that throws an exception on one fetch will be retried on the next
interval. No state is corrupted. The thread is not killed. The error is logged
(to stderr, which systemd's journal captures) and the loop sleeps for the normal
interval before trying again.

### Layer 3: Per-Source Resilience (at registration)

Network-dependent sources are registered inside a try/except:

```python
try:
    from app.streams.sources import WeatherStream, ISSTracker
    self.register(WeatherStream())
    self.register(ISSTracker())
except Exception:
    pass
```

If the import itself fails (perhaps `urllib.request` is not available in a
stripped-down Python build), the sources simply do not exist. The system runs
with whatever sources it can load.

### Layer 4: System-Level Resilience (the app factory)

In `app/__init__.py`, the stream engine is initialized after the display and
message queue, but before the blueprints. If the stream engine itself fails
to initialize, the rest of the app still works -- you just will not have live
data streams. The display, the web UI, the voice input, the API -- all functional.

This layered approach means the system degrades gracefully from "everything works"
through "some streams are missing" to "streams are broken but the display works"
to "the display is a plain message board." Each layer of failure removes some
functionality without collapsing the system.

## Running Multiple Streams

The engine supports running any number of streams simultaneously. Each stream runs
in its own daemon thread:

```bash
# Start system stats and weather
curl -X POST http://localhost:5000/api/streams/system_stats/start
curl -X POST http://localhost:5000/api/streams/weather/start

# Add the ISS tracker
curl -X POST http://localhost:5000/api/streams/iss_tracker/start

# Check what's running
curl http://localhost:5000/api/streams
```

The response from `/api/streams` shows all available sources and their status:

```json
{
  "streams": [
    {"name": "system_stats", "description": "Raspberry Pi system health...", "interval": 60, "active": true},
    {"name": "clock", "description": "Current time display...", "interval": 30, "active": false},
    {"name": "countdown", "description": "Countdown to a target time", "interval": 10, "active": false},
    {"name": "sensor_sim", "description": "Simulated lab sensor data...", "interval": 15, "active": false},
    {"name": "weather", "description": "Local weather...", "interval": 300, "active": true},
    {"name": "iss_tracker", "description": "ISS position...", "interval": 30, "active": true}
  ]
}
```

When multiple streams are active, their messages interleave in the queue. The
display might show a weather update, then a system stat, then the ISS position,
then the time -- cycling through whatever data is being produced. The message queue
handles ordering by priority, and within the same priority, by arrival time (FIFO).

The interleaving is natural, not orchestrated. There is no round-robin scheduler
or fair-share allocator. Each source produces messages at its own interval, and
the queue processes them in order. If the weather source and the ISS tracker both
produce a message at the same moment (both priority 0), whichever arrived first
displays first. In practice, the intervals are all different (30s, 60s, 300s), so
collisions are rare and resolve instantly.

### Stopping Streams

```bash
# Stop one stream
curl -X POST http://localhost:5000/api/streams/weather/stop

# Stop everything
curl -X POST http://localhost:5000/api/streams/stop-all
```

The `stop_stream` method sets the running flag to `False` and joins the thread
with a 5-second timeout:

```python
def stop_stream(self, name):
    self._running_flags[name] = False
    t = self._active.pop(name, None)
    if t and t.is_alive():
        t.join(timeout=5)
```

Thanks to the interruptible sleep, the thread notices the flag within 100ms and
exits cleanly. The `join(timeout=5)` is a safety net -- if the thread is blocked
in an HTTP request (the 10-second timeout in `urlopen`), the join prevents the
caller from waiting forever. In the worst case, a thread takes up to 10 seconds
to exit (if it is in the middle of a network call when stop is requested). In
practice, it is nearly instant.

## The API Endpoints

The stream API follows the same RESTful conventions as the rest of the application.
Here is the complete reference:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/streams` | List all available sources and their active status |
| `POST` | `/api/streams/<name>/start` | Start a specific data stream |
| `POST` | `/api/streams/<name>/stop` | Stop a specific data stream |
| `POST` | `/api/streams/stop-all` | Stop all active data streams |

All endpoints return JSON. The start endpoint returns 404 if the source name is
not recognized:

```bash
$ curl -X POST http://localhost:5000/api/streams/nonexistent/start
{"error": "Unknown source: nonexistent"}
```

Starting an already-running stream is safe -- the engine stops the existing
thread and starts a fresh one:

```python
def start_stream(self, name):
    source = self._sources.get(name)
    if source is None:
        raise ValueError(f'Unknown source: {name}')
    # Stop if already running
    self.stop_stream(name)
    # ... start new thread
```

This restart-on-start behavior means the API is idempotent: calling start
twice gives the same result as calling it once. No need for the client to
check whether a stream is already running before starting it.

## Writing Your Own Data Source

The power of the plugin architecture is that you can add new data sources without
modifying the engine, the API, or any other part of the system. You write a class,
register it, and it works.

Let us build a complete example: a data source that reads temperature from a
DS18B20 one-wire sensor connected to the Pi's GPIO.

### Step 1: The Source Class

```python
# app/streams/sources.py (add to existing file)

class DS18B20Temperature:
    """Real temperature sensor via Linux 1-wire interface.

    The DS18B20 is a digital temperature sensor connected to GPIO4.
    Linux exposes it as a virtual file:
      /sys/bus/w1/devices/28-xxxxxxxxxxxx/w1_slave

    The second line of this file contains the temperature in millidegrees:
      t=21375  ->  21.375 C
    """

    name = 'lab_temp'
    description = 'Lab temperature from DS18B20 sensor'
    interval = 30

    def __init__(self, device_id=None):
        self._device_id = device_id
        self._device_path = None

    def _find_device(self):
        """Find the 1-wire device path."""
        import glob
        if self._device_id:
            path = f'/sys/bus/w1/devices/{self._device_id}/w1_slave'
        else:
            # Auto-detect: find the first 28-* device
            matches = glob.glob('/sys/bus/w1/devices/28-*/w1_slave')
            path = matches[0] if matches else None
        self._device_path = path

    def fetch(self):
        if self._device_path is None:
            self._find_device()
        if self._device_path is None:
            return None  # No sensor found -- stay quiet

        try:
            with open(self._device_path) as f:
                lines = f.readlines()

            # Line 1 ends with YES if CRC is valid
            if 'YES' not in lines[0]:
                return None  # Bad read -- skip this cycle

            # Line 2 contains t=NNNNN
            temp_str = lines[1].split('t=')[1]
            temp_c = int(temp_str) / 1000

            text = f'LAB TEMP: {temp_c:.1f}C'
            return {'text': text, 'transition': 'typewriter'}

        except (FileNotFoundError, IndexError, ValueError):
            self._device_path = None  # Force re-detection next cycle
            return None
```

### Step 2: Registration

Add the source to the engine's `init_app` method, or register it after the app
is created:

```python
# In app/streams/engine.py, inside init_app():
try:
    from app.streams.sources import DS18B20Temperature
    self.register(DS18B20Temperature())
except Exception:
    pass

# Or externally, after app creation:
from app.streams.sources import DS18B20Temperature
app.streams.register(DS18B20Temperature())
```

### Step 3: Use It

```bash
curl -X POST http://localhost:5000/api/streams/lab_temp/start
```

That is it. The engine creates a thread, calls `fetch()` every 30 seconds, and
sends the results to the display queue. The API endpoints work automatically
because the engine dynamically builds the source list.

### Design Notes on the Example

Several patterns in this example are worth calling out:

**Lazy device detection.** The sensor path is not resolved at construction time
but on the first `fetch()`. This means the source can be registered at app
startup even if the sensor is not plugged in yet. Plug it in later and the next
fetch will find it.

**CRC validation.** The DS18B20's 1-wire protocol includes a CRC check. The Linux
driver reports `YES` on line 1 if the checksum is valid. Our source checks this
and discards bad reads rather than showing garbage data. This is sensor discipline:
bad data is worse than no data.

**Re-detection on error.** If reading the device fails (sensor disconnected,
file vanished), the source clears `_device_path` and will re-detect on the next
cycle. Unplug the sensor, plug it back in -- the stream recovers automatically.

**Silent failure.** The source returns `None` for all error conditions. No error
messages on the display. For a real sensor, the absence of data *is* the signal --
if `LAB TEMP:` stops appearing on the display, you know the sensor needs
attention.

### More Ideas

The plugin architecture makes any data source possible. Some ideas, each requiring
only a single class with a `fetch()` method:

| Source | Data | Interest |
|--------|------|----------|
| **MQTT subscriber** | Subscribe to a lab's IoT broker topic | Connect to any IoT ecosystem |
| **RSS feed** | Parse and display headlines from a feed URL | Conference announcements, arXiv papers |
| **Serial sensor** | Read an Arduino sensor over USB serial | Custom lab instruments |
| **Build status** | Poll GitHub Actions or Jenkins for CI/CD results | Show green/red build status |
| **Tide data** | Fetch from NOAA CO-OPS API | For coastal labs |
| **Air quality** | PurpleAir or government AQI APIs | Relevant for outdoor installations |
| **Earthquake feed** | USGS real-time earthquake data (GeoJSON) | Seismically active regions |
| **Bitcoin price** | CoinGecko API (no key required) | Conference crowd-pleaser |
| **Train schedule** | MBTA or local transit API | Show next departure from your stop |

Each follows the same pattern: initialize state in `__init__`, fetch data in
`fetch()`, format it for 30 characters, return a dict. The engine does the rest.

## How Streams Coexist with Everything Else

One of the most important aspects of the stream architecture is what it does *not*
do: it does not take over the display. Streams produce messages in the same queue
as web forms, voice commands, gesture inputs, webhooks, OpenClaw compositions, and
workshop submissions. This means:

**Streams interleave with user messages.** If someone types "HELLO WORLD" into the
web form while three streams are active, their message enters the queue at its
priority and gets displayed in order. The user does not have to stop the streams.

**Higher-priority inputs preempt streams.** A voice command (priority 3) jumps
ahead of all pending stream messages (priority 0). The display plays the voice
command first, then resumes with the stream data. This is the ambient/notification
duality working as designed -- ambient streams yield to active interaction.

**Generators take the display exclusively.** If you start a cellular automaton via
the generator engine (Chapter 15), it writes directly to the display buffer,
bypassing the queue entirely. Streams can still produce messages that queue up, but
they will not display until the generator stops and the queue resumes processing.
This is intentional -- a generative art display and a scrolling data readout
cannot coexist on 210 pixels.

**Playlists and streams can run together.** A playlist (Chapter 12) enqueues its
messages through the same queue. Stream messages and playlist messages interleave
naturally.

The practical result is that you can leave several streams running as a baseline --
system stats, weather, clock -- and layer other interactions on top. The display
has a "default mode" (showing ambient data) that gives way to "active mode"
(responding to users) and returns to default when the queue drains. No code is
needed to manage these transitions -- the priority queue handles it all.

## Exercises

These exercises progress from using the built-in streams to understanding the
architecture to building your own sources.

### Observe

1. **The rhythm of ambient data.** Start three streams simultaneously: system stats,
   weather, and the ISS tracker. Watch the display for 10 minutes. How do the
   messages interleave? Can you predict which stream will display next? How does the
   cadence feel -- too fast, too slow, or just right for ambient awareness?

2. **The clock as a benchmark.** Start the clock stream and check it against your
   phone. How many seconds off is it? Why? (Hint: consider the 30-second interval
   and the time spent in the queue.) Modify the interval to 10 seconds and observe
   the change in accuracy versus the change in flip frequency.

### Experiment

3. **Priority escalation.** Start the countdown stream with a 2-minute target.
   Simultaneously start the weather stream and system stats. Watch what happens
   when the countdown reaches zero. Does `TIME IS UP!` jump ahead of the weather
   data? What is the maximum delay between expiry and display, and why?

4. **Error resilience.** Start the weather stream, then disconnect from WiFi (or
   block the Open-Meteo domain with `/etc/hosts`). What appears on the display?
   How many error messages accumulate? Reconnect and observe the recovery. Now
   modify the weather source to return `None` instead of the error text. Which
   behavior do you prefer for a production installation?

5. **Load test.** Start all six built-in streams simultaneously. Monitor the Pi's
   CPU usage with `htop` or the system stats stream itself. How much CPU does the
   stream system consume? (The answer should be very little -- the threads spend
   almost all their time sleeping.) Now add a stream with `interval = 1`. What
   happens to the queue? To the display behavior? Where is the practical lower
   limit on interval?

### Create

6. **Build a real sensor stream.** If you have any sensor connected to your Pi
   (a DS18B20 temperature probe, a BME280 environmental sensor, an ADC reading a
   photoresistor), write a data source class for it. Follow the pattern from the
   worked example above. What `interval` is appropriate for your sensor's data?
   What should `fetch()` return when the sensor is disconnected?

7. **Build a network data source.** Choose a free, key-less API (suggestions:
   USGS earthquake feed at `earthquake.usgs.gov/fdsnws/event/1/query`, the
   CoinGecko price API, or your university's public event calendar) and write a
   data source for it. Focus on the formatting challenge: how do you compress the
   API response into 30 characters of uppercase text that is meaningful at a glance?

8. **Build an adaptive-interval source.** The built-in sources have fixed intervals.
   Design a source where the interval changes based on the data. For example: a
   weather source that polls every 5 minutes normally, but every 30 seconds when a
   storm is approaching. You will need to modify either the source (by returning a
   hint in the dict) or the engine (by allowing dynamic intervals). Which approach
   is cleaner? Why?

### Design

9. **Ambient information audit.** Walk through a building and catalog every piece
   of ambient information you can see (clocks, thermostats, exit signs, status
   lights on printers, etc.). For each, ask: could a flipdot display replace it?
   What would be gained or lost? Write a one-paragraph design brief for the most
   interesting replacement.

10. **Stream composition.** Design (on paper, not in code) a system where two
    streams *interact*: for example, a weather stream that changes the cellular
    automaton's parameters based on temperature (cold = slow tick, hot = fast tick),
    or a system-stats stream that adjusts the ISS tracker's interval based on CPU
    load. What architectural changes would the engine need to support this? Is this
    a good idea, or does it violate the separation between streams?

## Further Reading

- Weiser, M. & Brown, J.S. (1995). "Designing Calm Technology." Xerox PARC. --
  The foundational paper on ambient information design. Directly relevant to any
  physical display project.
- Ishii, H. & Ullmer, B. (1997). "Tangible Bits: Towards Seamless Interfaces
  between People, Bits and Atoms." *Proc. CHI '97*. -- Hiroshi Ishii's vision of
  ambient media, including early flipdot-like display experiments at MIT Media Lab.
- Mankoff, J. et al. (2003). "Heuristic Evaluation of Ambient Displays."
  *Proc. CHI '03*. -- Usability heuristics for peripheral displays. Useful if you
  want to evaluate your stream configurations rigorously.
- Open-Meteo documentation: `https://open-meteo.com/en/docs` -- The weather API
  used by the built-in weather source. Extensive documentation of parameters,
  endpoints, and WMO weather codes.
- "Where the ISS at?" REST API: `https://wheretheiss.at/w/developer` -- An
  alternative ISS tracking API with additional data (velocity, altitude, visibility).
- Dougan, C.E. & Maguire, M. (2019). "Ambient Display Design Space." In
  *Peripheral Interaction*. Springer. -- A taxonomy of ambient display types and
  their design parameters.

## What's Next

Chapter 17 builds on the stream infrastructure to add **webhook integration** --
the display no longer just polls for data, it receives pushes from external
systems. GitHub sends a commit notification; the display shows it. A lab instrument
finishes a run; the display announces the result. The architectural shift continues:
from polling to listening, from pull to push. But the message queue remains the
center of everything. All roads still lead to the queue.
