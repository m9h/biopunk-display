# Chapter 16: Live Data Streams

## A Window Into the Living World

Until now, the display shows what we tell it. This chapter flips that relationship:
the display starts *listening to the world* and reporting what it hears.

Weather, ISS position, system health, lab sensor readings — live data streams
transform the flipdot from a message board into an ambient information display.
Glance at it and know the temperature, the CPU load, or whether the International
Space Station is overhead.

## The Plugin Architecture

Each data source is a Python class with a simple interface:

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

The stream engine handles threading, scheduling, and queue integration. You write
the `fetch()` method; the engine does the rest.

This is the **Strategy pattern** in action: the algorithm (data fetching) varies
independently from the framework (scheduling, rendering, error handling).

## Built-in Sources

### System Stats

```
CPU 52C | LOAD 0.43 | MEM 67% | UP 148H
```

Reads directly from `/proc` and `/sys` — no dependencies, works on any Linux.
Perfect for monitoring the Pi itself. If the CPU temperature spikes, you'll
see it on the display before you feel the room get warmer.

### Clock

Shows the current time using the double-height font. Simple, but when your
flipdot display is mounted on a wall, it becomes the coolest clock in the
building. The dots clicking to update the minute is deeply satisfying.

### Countdown Timer

```
23M 45S
```

Counts down to a target time. Essential for workshops ("15 minutes left!"),
presentations, and lunch breaks. When time runs out, it sends a high-priority
`TIME IS UP!` with the flash transition.

### Sensor Simulator

Generates realistic sine-wave-modulated data that looks like real sensor
readings: temperature, humidity, CO2, light levels. Great for demos and
development when you don't have real sensors connected.

In production, replace this with actual sensor reads. The interface is
identical — just change what `fetch()` returns.

### Weather (Open-Meteo)

```
18C PARTLY CLOUDY WIND 12KPH
```

Uses the Open-Meteo API — **no API key required**. Free, open-source weather
data. The default location is Cambridge, MA (MIT area), configurable by
latitude/longitude.

WMO weather codes are mapped to readable text. The display becomes a physical
weather widget — more permanent than a phone notification, more ambient than
a screen.

### ISS Tracker

```
ISS: 42.3N -71.1W
```

Polls the ISS position every 30 seconds. When the station passes within 5
degrees of your location, it sends a high-priority alert:

```
ISS OVERHEAD NOW! LOOK UP!
```

This is science outreach at its best. A physical display that tells you when
to look at the sky.

## How Streams Interact with the Queue

All stream data flows through the same priority message queue as everything else:

```
Data Source → fetch() → Message Queue (priority 0) → Display
```

Streams use priority 0 by default — they're ambient information that yields to
voice commands, presence greetings, and workshop submissions. But individual
sources can set higher priorities for alerts (ISS overhead, timer expired).

## Running Multiple Streams

The engine supports multiple simultaneous streams:

```bash
# Start system stats and weather
curl -X POST http://localhost:5000/api/streams/system_stats/start
curl -X POST http://localhost:5000/api/streams/weather/start

# Check what's running
curl http://localhost:5000/api/streams

# Stop everything
curl -X POST http://localhost:5000/api/streams/stop-all
```

When multiple streams produce data simultaneously, the message queue handles
ordering. They interleave naturally — a weather update, then a system stat,
then the time.

## Writing Custom Sources

The power of this system is extensibility. Some ideas:

- **MQTT subscriber** — connect to a lab's IoT broker
- **Serial sensor** — read an Arduino sensor over USB
- **Social feed** — display mentions from a specific hashtag
- **Build status** — show CI/CD pipeline results (green/red)
- **Tide data** — for coastal labs
- **Air quality** — from PurpleAir or government APIs

Each is just a class with a `fetch()` method. Register it, start it, done.

## The Ambient Information Philosophy

The flipdot display excels at *ambient* information — data you absorb
peripherally without actively looking at a screen. You glance at it while
walking past. It's always there, always current, never demanding attention
but always available.

This is fundamentally different from notifications. A phone buzzes and demands
action. A flipdot display *is just there*, showing the temperature, showing the
time, showing that the ISS is overhead. It's information architecture for the
physical world.
