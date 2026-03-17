"""
Built-in data source plugins for the stream engine.

Each source implements:
  - name: str
  - description: str
  - interval: int (seconds)
  - fetch() -> dict with 'text' and/or 'bar_value'
"""

import time
import math
import random
import platform


class SystemStats:
    """System health: CPU temp, load, memory, uptime.

    Works on any Linux system — perfect for monitoring the Pi itself.
    No external dependencies.
    """

    name = 'system_stats'
    description = 'Raspberry Pi system health — CPU temp, load, memory'
    interval = 60  # every minute

    def fetch(self):
        parts = []

        # CPU temperature (Pi-specific but works on any Linux with thermal zone)
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                temp_c = int(f.read().strip()) / 1000
                parts.append(f'CPU {temp_c:.0f}C')
        except (FileNotFoundError, ValueError):
            pass

        # Load average
        try:
            with open('/proc/loadavg') as f:
                load = f.read().split()[0]
                parts.append(f'LOAD {load}')
        except (FileNotFoundError, ValueError):
            pass

        # Memory
        try:
            with open('/proc/meminfo') as f:
                lines = f.readlines()
                total = int(lines[0].split()[1])
                available = int(lines[2].split()[1])
                used_pct = int((1 - available / total) * 100)
                parts.append(f'MEM {used_pct}%')
        except (FileNotFoundError, ValueError, IndexError):
            pass

        # Uptime
        try:
            with open('/proc/uptime') as f:
                uptime_sec = float(f.read().split()[0])
                hours = int(uptime_sec // 3600)
                parts.append(f'UP {hours}H')
        except (FileNotFoundError, ValueError):
            pass

        text = ' | '.join(parts) if parts else f'{platform.node()} OK'
        return {'text': text, 'transition': 'righttoleft'}


class ClockStream:
    """Current time display — simple but essential for ambient mode.

    Shows the time in a large, clear format. When combined with the
    double-height font, it turns the flipdot into a very cool clock.
    """

    name = 'clock'
    description = 'Current time display (updates every 30s)'
    interval = 30

    def fetch(self):
        t = time.localtime()
        text = time.strftime('%H:%M', t)
        return {'text': text, 'transition': 'double_static'}


class CountdownStream:
    """Countdown timer — counts down from a target time.

    Useful for workshops, presentations, lunch breaks.
    Set COUNTDOWN_TARGET as epoch timestamp in config.
    """

    name = 'countdown'
    description = 'Countdown to a target time'
    interval = 10

    def __init__(self, target_epoch=None):
        # Default: 1 hour from now
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


class SensorSimulator:
    """Simulated lab sensor — generates realistic-looking readings.

    Produces sine-wave-modulated values that look like real sensor data:
    temperature, humidity, CO2, etc. Great for demos and testing.

    Replace this with real sensor reads (I2C, serial, MQTT) for production.
    """

    name = 'sensor_sim'
    description = 'Simulated lab sensor data (for demos)'
    interval = 15

    def __init__(self):
        self._t = 0
        self._sensors = [
            ('TEMP', 22, 3, 'C', 0.05),      # base, amplitude, unit, frequency
            ('HUMID', 45, 10, '%', 0.03),
            ('CO2', 420, 50, 'PPM', 0.02),
            ('LIGHT', 500, 200, 'LUX', 0.07),
        ]

    def fetch(self):
        self._t += 1
        # Pick a sensor to report (cycle through them)
        idx = self._t % len(self._sensors)
        name, base, amp, unit, freq = self._sensors[idx]

        value = base + amp * math.sin(self._t * freq) + random.gauss(0, amp * 0.1)
        text = f'{name}: {value:.1f} {unit}'

        return {'text': text, 'transition': 'typewriter'}


class WeatherStream:
    """Open-Meteo weather data — no API key required.

    Fetches current weather for a configured location using the free
    Open-Meteo API. Shows temperature, conditions, and wind.
    """

    name = 'weather'
    description = 'Local weather from Open-Meteo (no API key needed)'
    interval = 300  # every 5 minutes

    def __init__(self, lat=42.36, lon=-71.09):
        """Default: Cambridge, MA (MIT Media Lab area)."""
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

            # WMO weather codes to text
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


class ISSTracker:
    """International Space Station position tracker.

    Shows the ISS latitude/longitude and whether it's currently
    overhead (within ~500km of the configured location). When the
    ISS is overhead, it sends a high-priority alert.
    """

    name = 'iss_tracker'
    description = 'ISS position — alerts when overhead'
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

            # Simple distance check (not great-circle, but good enough for alerts)
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
