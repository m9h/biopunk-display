"""
Cellular automata engine for the flipdot display.

Provides a Grid abstraction over the 7×30 binary display and implementations
of several classic automata: Conway's Game of Life, Brian's Brain, 1D elementary
automata (Wolfram rules), and cyclic cellular automata.

All automata are pure functions: grid in, grid out. No hardware dependency.
The AutomataPlayer class bridges the automata to the display via a background thread.
"""

import random
import threading
import time
import copy


class Grid:
    """A 7×30 binary grid with toroidal (wrapping) boundaries."""

    def __init__(self, rows=7, cols=30):
        self.rows = rows
        self.cols = cols
        self._cells = [[0] * cols for _ in range(rows)]

    def get(self, row, col):
        """Get cell value with toroidal wrapping."""
        return self._cells[row % self.rows][col % self.cols]

    def set(self, row, col, val):
        """Set cell value with toroidal wrapping."""
        self._cells[row % self.rows][col % self.cols] = 1 if val else 0

    def randomize(self, density=0.5):
        """Fill grid with random cells at the given density."""
        for r in range(self.rows):
            for c in range(self.cols):
                self._cells[r][c] = 1 if random.random() < density else 0

    def clear(self):
        """Set all cells to 0."""
        for r in range(self.rows):
            for c in range(self.cols):
                self._cells[r][c] = 0

    def copy(self):
        """Return a deep copy of this grid."""
        new = Grid(self.rows, self.cols)
        new._cells = [row[:] for row in self._cells]
        return new

    def __eq__(self, other):
        if not isinstance(other, Grid):
            return NotImplemented
        return self.rows == other.rows and self.cols == other.cols and self._cells == other._cells

    def count_alive(self):
        """Count total living cells."""
        return sum(sum(row) for row in self._cells)

    def to_display_bytes(self):
        """Convert grid to 105-byte buffer for core.fill().

        Each of the 30 visible columns becomes one byte.
        Bit encoding: bit 0 = row 6 (bottom), bit 6 = row 0 (top).
        Columns 30-74 are padding (0x00).
        Columns 75-104 are padding (0x00) — used for double-height, not CA.
        """
        buf = [0] * 105
        for col in range(min(self.cols, 30)):
            byte_val = 0
            for row in range(min(self.rows, 7)):
                if self._cells[row][col]:
                    # row 0 (top) = bit 6, row 6 (bottom) = bit 0
                    byte_val |= (1 << (6 - row))
            buf[col] = byte_val
        return bytes(buf)

    @classmethod
    def from_display_bytes(cls, data, rows=7, cols=30):
        """Create a Grid from a 105-byte display buffer."""
        grid = cls(rows, cols)
        for col in range(min(cols, 30, len(data))):
            byte_val = data[col]
            for row in range(min(rows, 7)):
                if byte_val & (1 << (6 - row)):
                    grid._cells[row][col] = 1
        return grid

    def __repr__(self):
        lines = []
        for row in self._cells:
            lines.append(''.join('#' if c else '.' for c in row))
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Automata implementations — pure functions, no side effects
# ---------------------------------------------------------------------------

def game_of_life(grid):
    """Conway's Game of Life (B3/S23) with toroidal wrapping.

    Returns a new Grid representing the next generation.
    """
    new = Grid(grid.rows, grid.cols)
    for r in range(grid.rows):
        for c in range(grid.cols):
            neighbors = _moore_neighbors(grid, r, c)
            alive = grid.get(r, c)
            if alive:
                new.set(r, c, neighbors in (2, 3))
            else:
                new.set(r, c, neighbors == 3)
    return new


def brians_brain(grid, dying_grid):
    """Brian's Brain — 3-state automaton: alive -> dying -> dead.

    - Alive cells become dying
    - Dying cells become dead
    - Dead cells with exactly 2 alive neighbors become alive

    Args:
        grid: Grid of alive cells (1=alive, 0=not alive)
        dying_grid: Grid of dying cells (1=dying, 0=not dying)

    Returns:
        (new_grid, new_dying_grid)
    """
    new_alive = Grid(grid.rows, grid.cols)
    new_dying = Grid(grid.rows, grid.cols)

    for r in range(grid.rows):
        for c in range(grid.cols):
            is_alive = grid.get(r, c)
            is_dying = dying_grid.get(r, c)

            if is_alive:
                # Alive -> dying
                new_dying.set(r, c, 1)
            elif is_dying:
                # Dying -> dead (do nothing, already 0)
                pass
            else:
                # Dead: birth if exactly 2 alive neighbors
                neighbors = _moore_neighbors(grid, r, c)
                if neighbors == 2:
                    new_alive.set(r, c, 1)

    return new_alive, new_dying


def elementary_ca(grid, rule=30):
    """1D Wolfram elementary automaton.

    Treats row 0 as the newest generation. Each step:
    - Shifts all rows down by 1 (row 6 is dropped)
    - Computes new row 0 from previous row 0 using the rule number

    This creates an upward-scrolling pattern on the display.

    Args:
        grid: Current grid state
        rule: Wolfram rule number (0-255). Common: 30, 90, 110, 184

    Returns:
        New Grid with the next generation.
    """
    new = Grid(grid.rows, grid.cols)

    # Shift rows down: row[i] = old row[i-1]
    for r in range(grid.rows - 1, 0, -1):
        for c in range(grid.cols):
            new.set(r, c, grid.get(r - 1, c))

    # Compute new row 0 from old row 0
    for c in range(grid.cols):
        left = grid.get(0, c - 1)
        center = grid.get(0, c)
        right = grid.get(0, c + 1)
        pattern = (left << 2) | (center << 1) | right
        new.set(0, c, (rule >> pattern) & 1)

    return new


def cyclic_ca(grid, states_grid, num_states=4, threshold=1):
    """Cyclic cellular automaton.

    Each cell has a state 0..num_states-1. A cell advances to the next state
    if at least `threshold` of its Moore neighbors are in the next state.
    The binary grid shows state 0 as off, all other states as on.

    Args:
        grid: Binary display grid (derived from states)
        states_grid: List[List[int]] of actual state values
        num_states: Number of states in the cycle
        threshold: Neighbors needed to advance

    Returns:
        (new_grid, new_states_grid)
    """
    rows = len(states_grid)
    cols = len(states_grid[0]) if rows > 0 else 0
    new_states = [[0] * cols for _ in range(rows)]
    new_grid = Grid(rows, cols)

    for r in range(rows):
        for c in range(cols):
            current = states_grid[r][c]
            next_state = (current + 1) % num_states
            # Count neighbors in the next state
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (r + dr) % rows
                    nc = (c + dc) % cols
                    if states_grid[nr][nc] == next_state:
                        count += 1
            if count >= threshold:
                new_states[r][c] = next_state
            else:
                new_states[r][c] = current

            # Binary: state 0 = off, anything else = on
            new_grid.set(r, c, new_states[r][c] != 0)

    return new_grid, new_states


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _moore_neighbors(grid, row, col):
    """Count alive Moore neighbors (8-connected, toroidal)."""
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            if grid.get(row + dr, col + dc):
                count += 1
    return count


def random_states_grid(rows=7, cols=30, num_states=4):
    """Create a random states grid for cyclic CA."""
    return [[random.randint(0, num_states - 1) for _ in range(cols)]
            for _ in range(rows)]


# ---------------------------------------------------------------------------
# AutomataPlayer — bridges automata to the display
# ---------------------------------------------------------------------------

class AutomataPlayer:
    """Runs a cellular automaton on the flipdot display in a background thread."""

    def __init__(self, app, automaton='life', speed=0.3, **kwargs):
        self._app = app
        self._automaton = automaton
        self._speed = speed
        self._kwargs = kwargs
        self._thread = None
        self._running = False

        # State
        self._grid = Grid()
        self._grid.randomize(kwargs.get('density', 0.4))
        self._dying_grid = Grid()  # for Brian's Brain
        self._states_grid = None   # for cyclic CA

        if automaton == 'cyclic':
            num_states = kwargs.get('num_states', 4)
            self._states_grid = random_states_grid(num_states=num_states)
            # Derive initial binary grid from states
            for r in range(self._grid.rows):
                for c in range(self._grid.cols):
                    self._grid.set(r, c, self._states_grid[r][c] != 0)

        if automaton == 'elementary':
            # Start with a single cell in the center of row 0
            self._grid.clear()
            self._grid.set(0, self._grid.cols // 2, 1)

    def start(self):
        """Start the automaton in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f'automata-{self._automaton}'
        )
        self._thread.start()

    def stop(self):
        """Stop the automaton."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        """Main loop: step and display."""
        while self._running:
            self._step()
            # Interruptible sleep
            for _ in range(int(self._speed * 20)):
                if not self._running:
                    return
                time.sleep(0.05)

    def _step(self):
        """Advance one generation and send to display."""
        if self._automaton == 'life':
            self._grid = game_of_life(self._grid)
        elif self._automaton == 'brain':
            self._grid, self._dying_grid = brians_brain(
                self._grid, self._dying_grid
            )
        elif self._automaton == 'elementary':
            rule = self._kwargs.get('rule', 30)
            self._grid = elementary_ca(self._grid, rule=rule)
        elif self._automaton == 'cyclic':
            num_states = self._kwargs.get('num_states', 4)
            threshold = self._kwargs.get('threshold', 1)
            self._grid, self._states_grid = cyclic_ca(
                self._grid, self._states_grid,
                num_states=num_states, threshold=threshold
            )

        # Send to display
        display_bytes = self._grid.to_display_bytes()
        try:
            self._app.display.set_frame(display_bytes)
            self._app.display.core.fill(display_bytes)
        except Exception:
            pass  # no hardware — silently skip
