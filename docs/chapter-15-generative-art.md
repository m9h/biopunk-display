# Chapter 15: Generative Art & Cellular Automata

## A Tiny Universe of Clicking Dots

The flipdot display is a 7×30 grid — 210 electromagnetic cells that physically
flip between states. This isn't a metaphor for cellular automata. It *is* one.
Each dot is a cell, each frame is a generation, and the clicking sound of dots
flipping is the sound of computation made physical.

## What Are Cellular Automata?

A cellular automaton is a grid of cells, each in one of a finite number of states
(for us: on or off). At each time step, every cell updates based on a simple rule
that considers its neighbors. From these local rules, complex global patterns
emerge — a phenomenon called **emergence**.

This is the same mechanism behind:
- Pattern formation in biology (Turing patterns → animal stripes, coral structures)
- Self-organization in physics (crystal growth, sand dunes)
- Computation theory (Rule 110 is Turing-complete)

## The Generator Engine

The engine is a simple framework: generators produce 7×30 boolean grids, and the
engine renders them to hardware at a configurable tick rate.

```python
class GeneratorEngine:
    def start(self, name, seed=None, tick_rate=None):
        gen = self._generators[name]
        gen.reset(seed=seed)
        # Background thread: tick → render → sleep → repeat
```

### Grid to Bytes

Converting a boolean grid to the flipdot's byte format:

```python
def _grid_to_bytes(self, grid):
    buf = [0] * 105
    for col in range(30):
        byte_val = 0
        for row in range(7):
            if grid[row][col]:
                byte_val |= (1 << row)
        buf[col] = byte_val
    return bytes(buf)
```

Each column is one byte, with bits 0-6 mapping to rows 0-6. The display hardware
handles the rest — flipping physical dots to match the buffer.

## The Algorithms

### Conway's Game of Life

The most famous cellular automaton. Three rules:
1. A live cell with 2 or 3 neighbors **survives**
2. A dead cell with exactly 3 neighbors is **born**
3. All other cells **die**

On a 7-row toroidal grid (wrapping top-to-bottom and left-to-right), patterns
evolve quickly. Gliders cross the screen in seconds. Oscillators blink. Chaos
settles into order, then erupts again.

```python
# ~35% initial density gives the most interesting evolution
self.grid = [[rng.random() < 0.35 for _ in range(30)] for _ in range(7)]
```

The 35% figure is deliberate — too sparse and the grid dies, too dense and it
chokes. This "edge of chaos" produces the most dynamic behavior.

### Wolfram Rules (Rule 30, Rule 110)

Elementary 1D cellular automata, invented by Stephen Wolfram. Each cell looks at
itself and its two neighbors (3 bits = 8 possible patterns), and a rule number
(0-255) determines the output for each pattern.

The display shows this as a **spacetime diagram**: the current generation is at
the bottom, and previous generations scroll upward. You see 7 generations at once.

- **Rule 30**: Starting from a single dot, it produces seemingly random chaos.
  It's used as a random number generator in Mathematica.
- **Rule 110**: Also starts from simple conditions but produces complex, structured
  behavior. It was proven Turing-complete by Matthew Cook — meaning this simple
  rule can compute anything a computer can.

Watching Rule 110 unfold on a physical display, with dots clicking into place, is
a vivid demonstration that computation doesn't require silicon.

### Reaction-Diffusion

Inspired by Alan Turing's 1952 paper "The Chemical Basis of Morphogenesis." Two
chemicals (activator and inhibitor) diffuse at different rates and react with each
other, creating stable patterns: spots, stripes, spirals.

This is how leopards get their spots, how coral forms branching structures, and
how neurons self-organize during development. We use a simplified Gray-Scott model
thresholded to binary for the flipdot's on/off constraint.

The patterns are abstract on a 7-row grid, but mesmerizing — bands of dots form,
dissolve, and reform in slow waves.

### Random Spark (Fireflies)

Not a true automaton, but a beautiful generative pattern. Dots appear and fade
with a probability that varies sinusoidally over time and space, creating waves
of density that sweep across the display — like watching fireflies in a field.

## API

```bash
# List available generators
curl http://localhost:5000/api/generators

# Start Game of Life
curl -X POST http://localhost:5000/api/generators/start \
  -H 'Content-Type: application/json' \
  -d '{"name": "game_of_life", "tick_rate": 0.5}'

# Start Rule 30
curl -X POST http://localhost:5000/api/generators/start \
  -d '{"name": "wolfram_rule_30"}'

# Stop
curl -X POST http://localhost:5000/api/generators/stop
```

## Writing Your Own Generator

Any class with `name`, `description`, `reset(seed)`, and `tick() -> grid` works:

```python
class MyPattern:
    name = 'my_pattern'
    description = 'My custom pattern'

    def reset(self, seed=None): ...
    def tick(self):
        return [[bool] * 30 for _ in range(7)]

# Register it:
app.generators.register(MyPattern())
```

## Educational Value

Running cellular automata on physical hardware bridges the gap between abstract
math and tangible experience. Students can *hear* the difference between Rule 30
(chaotic clicking) and Rule 110 (structured, rhythmic). They can watch emergence
happen — not on a screen, but in a physical grid of electromagnetic dots.

The seed parameter makes experiments reproducible. The same seed produces the same
evolution, which is essential for science: observe, hypothesize, test, repeat.
