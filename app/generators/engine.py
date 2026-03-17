"""
Generator engine — runs a generative art algorithm on the flipdot display.

Each generator is a class with:
  - reset(seed=None)  — initialize state
  - tick() -> grid    — advance one generation, return 7×30 bool grid
  - name              — human-readable name

The engine runs the selected generator in a background thread, converting
each grid to the display's byte format and sending it via the core driver.
"""

import threading
import time
import sys

# Display dimensions (visible area)
ROWS = 7
COLS = 30


class GeneratorEngine:
    """Runs generative art algorithms on the flipdot display."""

    def __init__(self, app=None):
        self._app = None
        self._thread = None
        self._running = False
        self._generator = None
        self._tick_rate = 0.3  # seconds between generations
        self._generators = {}
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._tick_rate = app.config.get('GENERATOR_TICK_RATE', 0.3)

        # Register built-in generators
        from app.generators.automata import (
            GameOfLife, WolframRule, ReactionDiffusion, RandomSpark
        )
        self.register(GameOfLife())
        self.register(WolframRule(rule=30))
        self.register(WolframRule(rule=110))
        self.register(ReactionDiffusion())
        self.register(RandomSpark())

        app.generators = self

    def register(self, generator):
        """Register a generator by name."""
        self._generators[generator.name] = generator

    def list_generators(self):
        """Return list of available generator names and descriptions."""
        return [
            {'name': g.name, 'description': g.description}
            for g in self._generators.values()
        ]

    @property
    def active(self):
        """Name of currently running generator, or None."""
        if self._thread and self._thread.is_alive() and self._generator:
            return self._generator.name
        return None

    def start(self, name, seed=None, tick_rate=None):
        """Start a generator by name."""
        self.stop()

        gen = self._generators.get(name)
        if gen is None:
            raise ValueError(f'Unknown generator: {name}')

        gen.reset(seed=seed)
        self._generator = gen
        if tick_rate is not None:
            self._tick_rate = tick_rate

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name='generator'
        )
        self._thread.start()
        print(f'[generator] Started: {name}', file=sys.stderr)

    def stop(self):
        """Stop the current generator."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._generator = None

    def _run_loop(self):
        """Tick the generator and render each frame to the display."""
        display = self._app.display

        while self._running:
            try:
                grid = self._generator.tick()
                frame = self._grid_to_bytes(grid)
                with display._lock:
                    display.core.fill(frame)
            except Exception as e:
                print(f'[generator] Error: {e}', file=sys.stderr)
                break

            # Interruptible sleep
            for _ in range(int(self._tick_rate * 20)):
                if not self._running:
                    return
                time.sleep(0.05)

    def _grid_to_bytes(self, grid):
        """Convert a 7×30 bool grid to the 105-byte display buffer.

        The flipdot display maps columns 0-29 as the visible area.
        Each byte represents one column, with bits 0-6 mapping to rows 0-6.
        BITMASK = [1, 2, 4, 8, 0x10, 0x20, 0x40]
        """
        buf = [0] * 105  # full buffer (105 cols, only 0-29 visible)

        for col in range(min(COLS, len(grid[0]) if grid else 0)):
            byte_val = 0
            for row in range(ROWS):
                if row < len(grid) and col < len(grid[row]) and grid[row][col]:
                    byte_val |= (1 << row)
            buf[col] = byte_val

        return bytes(buf)
