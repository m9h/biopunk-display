"""
Built-in generative art algorithms for the flipdot display.

Each class implements:
  - name: str
  - description: str
  - reset(seed=None)
  - tick() -> list[list[bool]]  (7 rows × 30 cols)
"""

import random

ROWS = 7
COLS = 30


class GameOfLife:
    """Conway's Game of Life on a 7×30 toroidal grid.

    The classic: cells live or die based on their neighbor count.
    On a 7-row display, patterns evolve quickly — gliders cross
    the screen in seconds, and you hear each generation click.
    """

    name = 'game_of_life'
    description = "Conway's Game of Life — birth, survival, death on a toroidal grid"

    def __init__(self):
        self.grid = [[False] * COLS for _ in range(ROWS)]

    def reset(self, seed=None):
        rng = random.Random(seed)
        # ~35% density gives interesting evolution
        self.grid = [
            [rng.random() < 0.35 for _ in range(COLS)]
            for _ in range(ROWS)
        ]

    def tick(self):
        new = [[False] * COLS for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                n = self._neighbors(r, c)
                if self.grid[r][c]:
                    new[r][c] = n in (2, 3)  # survival
                else:
                    new[r][c] = n == 3  # birth
        self.grid = new
        return self.grid

    def _neighbors(self, r, c):
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr = (r + dr) % ROWS  # toroidal wrap
                nc = (c + dc) % COLS
                if self.grid[nr][nc]:
                    count += 1
        return count


class WolframRule:
    """1D elementary cellular automaton (Wolfram rules).

    Renders one generation per row, scrolling upward. The 7-row display
    shows the last 7 generations at once — a spacetime diagram you can
    watch unfold.

    Rule 30 produces chaos from a single cell. Rule 110 is Turing-complete.
    """

    description_template = "Wolfram Rule {} — 1D automaton scrolling upward"

    def __init__(self, rule=30):
        self.rule = rule
        self.name = f'wolfram_rule_{rule}'
        self.description = self.description_template.format(rule)
        self.state = [False] * COLS
        self.history = []

    def reset(self, seed=None):
        if seed == 'random':
            rng = random.Random()
            self.state = [rng.random() < 0.5 for _ in range(COLS)]
        else:
            # Default: single cell in center
            self.state = [False] * COLS
            self.state[COLS // 2] = True
        self.history = [list(self.state)]

    def tick(self):
        new_state = [False] * COLS
        for i in range(COLS):
            left = self.state[(i - 1) % COLS]
            center = self.state[i]
            right = self.state[(i + 1) % COLS]
            # 3-bit neighborhood → rule bit index
            index = (int(left) << 2) | (int(center) << 1) | int(right)
            new_state[i] = bool(self.rule & (1 << index))

        self.state = new_state
        self.history.append(list(self.state))

        # Keep only last ROWS generations
        if len(self.history) > ROWS:
            self.history = self.history[-ROWS:]

        # Pad history to ROWS if needed
        grid = [[False] * COLS] * (ROWS - len(self.history)) + self.history
        return grid


class ReactionDiffusion:
    """Simplified reaction-diffusion on a 7×30 grid.

    Inspired by Turing patterns — the mechanism behind leopard spots,
    zebra stripes, and coral structures. On a 7-row grid, the patterns
    are abstract but mesmerizing: bands of dots form, dissolve, reform.

    This is a thresholded Gray-Scott-like model, simplified for the
    binary (on/off) constraint of flipdots.
    """

    name = 'reaction_diffusion'
    description = 'Turing-inspired reaction-diffusion patterns'

    def __init__(self):
        self.u = [[0.0] * COLS for _ in range(ROWS)]
        self.v = [[0.0] * COLS for _ in range(ROWS)]

    def reset(self, seed=None):
        rng = random.Random(seed)
        self.u = [[1.0] * COLS for _ in range(ROWS)]
        self.v = [[0.0] * COLS for _ in range(ROWS)]
        # Seed a few random patches of activator
        for _ in range(3):
            r = rng.randint(1, ROWS - 2)
            c = rng.randint(1, COLS - 2)
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    rr = (r + dr) % ROWS
                    cc = (c + dc) % COLS
                    self.v[rr][cc] = 1.0
                    self.u[rr][cc] = 0.5

    def tick(self):
        # Gray-Scott parameters (tuned for small grid)
        Du, Dv = 0.16, 0.08
        f, k = 0.035, 0.065
        dt = 1.0

        new_u = [[0.0] * COLS for _ in range(ROWS)]
        new_v = [[0.0] * COLS for _ in range(ROWS)]

        for r in range(ROWS):
            for c in range(COLS):
                # Laplacian (5-point stencil, toroidal)
                lap_u = (
                    self.u[(r - 1) % ROWS][c] + self.u[(r + 1) % ROWS][c] +
                    self.u[r][(c - 1) % COLS] + self.u[r][(c + 1) % COLS] -
                    4 * self.u[r][c]
                )
                lap_v = (
                    self.v[(r - 1) % ROWS][c] + self.v[(r + 1) % ROWS][c] +
                    self.v[r][(c - 1) % COLS] + self.v[r][(c + 1) % COLS] -
                    4 * self.v[r][c]
                )

                uvv = self.u[r][c] * self.v[r][c] * self.v[r][c]
                new_u[r][c] = self.u[r][c] + dt * (Du * lap_u - uvv + f * (1 - self.u[r][c]))
                new_v[r][c] = self.v[r][c] + dt * (Dv * lap_v + uvv - (f + k) * self.v[r][c])

                # Clamp
                new_u[r][c] = max(0, min(1, new_u[r][c]))
                new_v[r][c] = max(0, min(1, new_v[r][c]))

        self.u = new_u
        self.v = new_v

        # Threshold v to binary for the flipdots
        return [[self.v[r][c] > 0.25 for c in range(COLS)] for r in range(ROWS)]


class RandomSpark:
    """Random sparks — dots appear and fade like fireflies.

    A simple but beautiful pattern: random dots light up with a
    probability that varies sinusoidally over time, creating waves
    of density across the display.
    """

    name = 'random_spark'
    description = 'Firefly-like random sparks with density waves'

    def __init__(self):
        self.t = 0
        self.grid = [[False] * COLS for _ in range(ROWS)]

    def reset(self, seed=None):
        self.t = 0
        self.grid = [[False] * COLS for _ in range(ROWS)]

    def tick(self):
        import math
        self.t += 1

        # Base density oscillates between 5% and 40%
        density = 0.225 + 0.175 * math.sin(self.t * 0.1)

        # Spatial wave: density varies across columns
        new_grid = [[False] * COLS for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                local_density = density + 0.15 * math.sin((c + self.t) * 0.3)
                local_density = max(0, min(1, local_density))

                # Mix of new random and persistence from previous frame
                if self.grid[r][c]:
                    # Lit dots have 60% chance of staying lit (creates trails)
                    new_grid[r][c] = random.random() < 0.6
                else:
                    new_grid[r][c] = random.random() < local_density * 0.3

        self.grid = new_grid
        return self.grid
