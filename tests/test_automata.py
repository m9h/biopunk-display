"""Tests for cellular automata engine (app/display/automata.py).

All tests are pure logic — no hardware or Flask app required.
"""

import pytest

from app.display.automata import (
    Grid,
    game_of_life,
    brians_brain,
    elementary_ca,
    cyclic_ca,
    random_states_grid,
    _moore_neighbors,
)


# ===========================================================================
# Grid basics
# ===========================================================================

class TestGrid:

    def test_default_size(self):
        g = Grid()
        assert g.rows == 7
        assert g.cols == 30

    def test_custom_size(self):
        g = Grid(10, 20)
        assert g.rows == 10
        assert g.cols == 20

    def test_initially_empty(self):
        g = Grid()
        assert g.count_alive() == 0

    def test_set_and_get(self):
        g = Grid()
        g.set(3, 15, 1)
        assert g.get(3, 15) == 1
        assert g.get(3, 14) == 0

    def test_set_false_clears(self):
        g = Grid()
        g.set(0, 0, 1)
        g.set(0, 0, 0)
        assert g.get(0, 0) == 0

    def test_toroidal_wrapping_row(self):
        g = Grid(7, 30)
        g.set(0, 5, 1)
        assert g.get(7, 5) == 1   # wraps to row 0
        assert g.get(-7, 5) == 1  # negative wraps too

    def test_toroidal_wrapping_col(self):
        g = Grid(7, 30)
        g.set(3, 0, 1)
        assert g.get(3, 30) == 1  # wraps to col 0
        assert g.get(3, -30) == 1

    def test_copy_is_independent(self):
        g = Grid()
        g.set(1, 1, 1)
        c = g.copy()
        c.set(1, 1, 0)
        assert g.get(1, 1) == 1  # original unchanged

    def test_equality(self):
        a = Grid()
        b = Grid()
        assert a == b
        a.set(0, 0, 1)
        assert a != b
        b.set(0, 0, 1)
        assert a == b

    def test_clear(self):
        g = Grid()
        g.randomize(1.0)
        g.clear()
        assert g.count_alive() == 0

    def test_randomize_density(self):
        g = Grid(7, 30)
        g.randomize(density=0.5)
        alive = g.count_alive()
        total = 7 * 30
        # Should be roughly 50% — allow wide margin for small grid
        assert 20 < alive < total - 20

    def test_randomize_full(self):
        g = Grid()
        g.randomize(density=1.0)
        assert g.count_alive() == 7 * 30

    def test_randomize_empty(self):
        g = Grid()
        g.randomize(density=0.0)
        assert g.count_alive() == 0


# ===========================================================================
# Display byte conversion
# ===========================================================================

class TestDisplayBytes:

    def test_empty_grid_produces_all_zeros(self):
        g = Grid()
        data = g.to_display_bytes()
        assert len(data) == 105
        assert all(b == 0 for b in data)

    def test_output_length_is_105(self):
        g = Grid()
        g.randomize()
        assert len(g.to_display_bytes()) == 105

    def test_top_row_sets_bit_6(self):
        g = Grid()
        g.set(0, 0, 1)  # row 0 (top)
        data = g.to_display_bytes()
        assert data[0] == 0x40  # bit 6

    def test_bottom_row_sets_bit_0(self):
        g = Grid()
        g.set(6, 0, 1)  # row 6 (bottom)
        data = g.to_display_bytes()
        assert data[0] == 0x01  # bit 0

    def test_all_rows_set_produces_0x7F(self):
        g = Grid()
        for r in range(7):
            g.set(r, 5, 1)
        data = g.to_display_bytes()
        assert data[5] == 0x7F

    def test_columns_30_to_74_are_zero(self):
        g = Grid()
        g.randomize(1.0)
        data = g.to_display_bytes()
        assert all(b == 0 for b in data[30:75])

    def test_columns_75_to_104_are_zero(self):
        g = Grid()
        g.randomize(1.0)
        data = g.to_display_bytes()
        assert all(b == 0 for b in data[75:])

    def test_round_trip(self):
        g = Grid()
        g.randomize(0.5)
        data = g.to_display_bytes()
        restored = Grid.from_display_bytes(data)
        assert g == restored

    def test_round_trip_specific_pattern(self):
        g = Grid()
        # Set a known pattern
        g.set(0, 0, 1)
        g.set(3, 15, 1)
        g.set(6, 29, 1)
        data = g.to_display_bytes()
        restored = Grid.from_display_bytes(data)
        assert restored.get(0, 0) == 1
        assert restored.get(3, 15) == 1
        assert restored.get(6, 29) == 1
        assert g == restored


# ===========================================================================
# Game of Life
# ===========================================================================

class TestGameOfLife:

    def test_empty_stays_empty(self):
        g = Grid()
        result = game_of_life(g)
        assert result.count_alive() == 0

    def test_block_still_life(self):
        """2x2 block is a still life — shouldn't change."""
        g = Grid()
        for r, c in [(1, 1), (1, 2), (2, 1), (2, 2)]:
            g.set(r, c, 1)
        result = game_of_life(g)
        assert result == g

    def test_blinker_oscillator(self):
        """Horizontal blinker should become vertical, then back."""
        g = Grid()
        # Horizontal: (3,14), (3,15), (3,16)
        g.set(3, 14, 1)
        g.set(3, 15, 1)
        g.set(3, 16, 1)

        gen1 = game_of_life(g)
        # Should be vertical: (2,15), (3,15), (4,15)
        assert gen1.get(2, 15) == 1
        assert gen1.get(3, 15) == 1
        assert gen1.get(4, 15) == 1
        assert gen1.get(3, 14) == 0
        assert gen1.get(3, 16) == 0
        assert gen1.count_alive() == 3

        gen2 = game_of_life(gen1)
        # Should be back to horizontal
        assert gen2 == g

    def test_lonely_cell_dies(self):
        g = Grid()
        g.set(3, 3, 1)
        result = game_of_life(g)
        assert result.get(3, 3) == 0

    def test_overcrowded_cell_dies(self):
        """Cell with 4+ neighbors dies."""
        g = Grid()
        # Center cell with 4 neighbors
        g.set(3, 15, 1)
        g.set(2, 15, 1)
        g.set(4, 15, 1)
        g.set(3, 14, 1)
        g.set(3, 16, 1)
        result = game_of_life(g)
        assert result.get(3, 15) == 0  # dies from overcrowding

    def test_birth_with_three_neighbors(self):
        """Dead cell with exactly 3 neighbors comes alive."""
        g = Grid()
        g.set(2, 14, 1)
        g.set(2, 15, 1)
        g.set(2, 16, 1)
        result = game_of_life(g)
        # (1,15) and (3,15) should be born
        assert result.get(1, 15) == 1
        assert result.get(3, 15) == 1

    def test_toroidal_wrapping(self):
        """Cells on edges interact with cells on the opposite edge."""
        g = Grid()
        # Three cells at the top-right corner wrapping around
        g.set(0, 29, 1)
        g.set(0, 0, 1)  # wraps from right edge
        g.set(0, 1, 1)
        result = game_of_life(g)
        # Row 6 (wrapping from top) col 0 should be born
        assert result.get(6, 0) == 1


# ===========================================================================
# Brian's Brain
# ===========================================================================

class TestBriansBrain:

    def test_alive_becomes_dying(self):
        g = Grid()
        d = Grid()
        g.set(3, 3, 1)
        new_g, new_d = brians_brain(g, d)
        assert new_g.get(3, 3) == 0   # no longer alive
        assert new_d.get(3, 3) == 1   # now dying

    def test_dying_becomes_dead(self):
        g = Grid()
        d = Grid()
        d.set(3, 3, 1)
        new_g, new_d = brians_brain(g, d)
        assert new_g.get(3, 3) == 0
        assert new_d.get(3, 3) == 0  # dead

    def test_birth_with_two_neighbors(self):
        g = Grid()
        d = Grid()
        g.set(2, 14, 1)
        g.set(2, 16, 1)
        # Cell (3,15) has 2 alive neighbors
        new_g, new_d = brians_brain(g, d)
        assert new_g.get(3, 15) == 1  # born

    def test_no_birth_with_one_neighbor(self):
        g = Grid()
        d = Grid()
        g.set(2, 14, 1)
        new_g, _ = brians_brain(g, d)
        assert new_g.get(3, 15) == 0

    def test_no_birth_with_three_neighbors(self):
        """Brian's Brain uses B2, not B3."""
        g = Grid()
        d = Grid()
        g.set(2, 14, 1)
        g.set(2, 15, 1)
        g.set(2, 16, 1)
        new_g, _ = brians_brain(g, d)
        assert new_g.get(3, 15) == 0  # 3 neighbors, not 2

    def test_full_lifecycle(self):
        """alive -> dying -> dead in 2 steps."""
        g = Grid()
        d = Grid()
        g.set(0, 0, 1)

        g1, d1 = brians_brain(g, d)
        assert d1.get(0, 0) == 1  # dying

        g2, d2 = brians_brain(g1, d1)
        assert g2.get(0, 0) == 0
        assert d2.get(0, 0) == 0  # dead


# ===========================================================================
# Elementary CA
# ===========================================================================

class TestElementaryCA:

    def test_rule_30_single_cell(self):
        """Rule 30 from a single center cell produces known pattern."""
        g = Grid(7, 30)
        g.set(0, 15, 1)

        result = elementary_ca(g, rule=30)
        # Row 0 should be the new generation computed from old row 0
        # Old row 0: ...010...  For center cell (15):
        # left=0, center=1, right=0 -> pattern 010=2 -> rule 30 bit 2 = 1
        assert result.get(0, 15) == 1
        # left=0, center=0, right=1 -> pattern 001=1 -> rule 30 bit 1 = 1
        assert result.get(0, 14) == 1
        # left=1, center=0, right=0 -> pattern 100=4 -> rule 30 bit 4 = 1
        assert result.get(0, 16) == 1

    def test_rows_shift_down(self):
        """Old row 0 should become row 1 after one step."""
        g = Grid(7, 30)
        g.set(0, 10, 1)
        result = elementary_ca(g, rule=30)
        assert result.get(1, 10) == 1  # shifted down

    def test_bottom_row_dropped(self):
        """Row 6 content is lost when rows shift down."""
        g = Grid(7, 30)
        g.set(6, 5, 1)
        result = elementary_ca(g, rule=30)
        assert result.get(6, 5) == 0  # was in row 5 which was empty

    def test_rule_90_produces_sierpinski(self):
        """Rule 90 is XOR — left XOR right."""
        g = Grid(7, 30)
        g.set(0, 15, 1)
        result = elementary_ca(g, rule=90)
        # Rule 90: pattern 001=1->bit1=1, pattern 010=2->bit2=0, pattern 100=4->bit4=1
        assert result.get(0, 14) == 1  # left neighbor
        assert result.get(0, 15) == 0  # center dies in rule 90
        assert result.get(0, 16) == 1  # right neighbor


# ===========================================================================
# Cyclic CA
# ===========================================================================

class TestCyclicCA:

    def test_cell_advances_with_enough_neighbors(self):
        states = [[0] * 5 for _ in range(5)]
        states[2][2] = 0  # current state
        # Put 1 neighbor in the next state (state 1)
        states[1][2] = 1
        g = Grid(5, 5)
        new_g, new_s = cyclic_ca(g, states, num_states=4, threshold=1)
        assert new_s[2][2] == 1  # advanced to next state

    def test_cell_stays_without_enough_neighbors(self):
        states = [[0] * 5 for _ in range(5)]
        states[2][2] = 0
        g = Grid(5, 5)
        new_g, new_s = cyclic_ca(g, states, num_states=4, threshold=1)
        assert new_s[2][2] == 0  # no neighbors in next state

    def test_binary_grid_reflects_states(self):
        states = [[0] * 5 for _ in range(5)]
        states[0][0] = 2  # non-zero state
        g = Grid(5, 5)
        new_g, _ = cyclic_ca(g, states, num_states=4, threshold=1)
        # State 2 should show as on (unless it advanced)
        # Since no neighbor is in state 3, it stays at 2 -> on
        assert new_g.get(0, 0) == 1

    def test_state_wraps_around(self):
        states = [[0] * 5 for _ in range(5)]
        states[2][2] = 3  # last state
        states[1][2] = 0  # next state wraps to 0
        g = Grid(5, 5)
        new_g, new_s = cyclic_ca(g, states, num_states=4, threshold=1)
        assert new_s[2][2] == 0  # wrapped around


# ===========================================================================
# Moore neighbors helper
# ===========================================================================

class TestMooreNeighbors:

    def test_isolated_cell(self):
        g = Grid()
        g.set(3, 15, 1)
        assert _moore_neighbors(g, 3, 15) == 0

    def test_surrounded_cell(self):
        g = Grid()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                g.set(3 + dr, 15 + dc, 1)
        assert _moore_neighbors(g, 3, 15) == 8  # all 8 neighbors

    def test_corner_wrapping(self):
        g = Grid(7, 30)
        g.set(6, 29, 1)  # bottom-right corner neighbor of (0,0) via wrapping
        assert _moore_neighbors(g, 0, 0) == 1
