"""
tests/test_grid.py
Tests unitaires pour core/grid.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from core.grid import (
    Cell, CellType, Floor, GridModel,
    GRID_SIZE, HALF,
)


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------

class TestCell(unittest.TestCase):

    def test_default_is_empty(self):
        c = Cell()
        assert c.cell_type == CellType.EMPTY
        assert c.custom_image is None

    def test_is_empty(self):
        assert Cell().is_empty()
        assert not Cell(CellType.GROUND).is_empty()

    def test_is_passable(self):
        assert Cell(CellType.GROUND).is_passable()
        assert Cell(CellType.ENEMY).is_passable()
        assert not Cell(CellType.WALL).is_passable()
        assert not Cell(CellType.EMPTY).is_passable()

    def test_clone(self):
        c = Cell(CellType.BOSS, "boss.png")
        clone = c.clone()
        assert clone.cell_type == CellType.BOSS
        assert clone.custom_image == "boss.png"
        assert clone is not c

    def test_to_dict_from_dict_roundtrip(self):
        c = Cell(CellType.TREASURE, "chest.png")
        d = c.to_dict()
        assert d == {"type": "treasure", "custom_image": "chest.png"}
        c2 = Cell.from_dict(d)
        assert c2.cell_type == CellType.TREASURE
        assert c2.custom_image == "chest.png"

    def test_from_dict_null_custom_image(self):
        c = Cell.from_dict({"type": "ground", "custom_image": None})
        assert c.custom_image is None


# ---------------------------------------------------------------------------
# CellType
# ---------------------------------------------------------------------------

class TestCellType(unittest.TestCase):

    def test_all_types_have_string_value(self):
        for ct in CellType:
            assert isinstance(ct.value, str)
            assert len(ct.value) > 0

    def test_from_string(self):
        assert CellType("ground") == CellType.GROUND
        assert CellType("stairs_down") == CellType.STAIRS_DOWN

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            CellType("invalid_type")


# ---------------------------------------------------------------------------
# Floor
# ---------------------------------------------------------------------------

class TestFloor(unittest.TestCase):

    def test_default_grid_is_72x72_empty(self):
        floor = Floor(floor_id=1, name="Test")
        assert len(floor.grid) == GRID_SIZE
        assert all(len(row) == GRID_SIZE for row in floor.grid)
        assert all(
            cell.cell_type == CellType.EMPTY
            for row in floor.grid
            for cell in row
        )

    def test_set_and_get_cell(self):
        floor = Floor(1, "F")
        floor.set_cell(0, 0, CellType.WALL)
        assert floor.get_cell(0, 0).cell_type == CellType.WALL

    def test_set_cell_out_of_bounds(self):
        floor = Floor(1, "F")
        with self.assertRaises(IndexError):
            floor.set_cell(72, 0, CellType.WALL)
        with self.assertRaises(IndexError):
            floor.set_cell(0, 72, CellType.WALL)
        with self.assertRaises(IndexError):
            floor.set_cell(-1, 0, CellType.WALL)

    def test_set_cell_at_coords(self):
        floor = Floor(1, "F")
        # (0, 0) → row = HALF-1-0 = 35, col = HALF+0 = 36
        floor.set_cell_at(0, 0, CellType.STAIRS_DOWN)
        assert floor.grid[HALF - 1][HALF].cell_type == CellType.STAIRS_DOWN

    def test_get_cell_at_coords(self):
        floor = Floor(1, "F")
        floor.grid[HALF - 1][HALF] = Cell(CellType.SPAWN)
        assert floor.get_cell_at(0, 0).cell_type == CellType.SPAWN

    def test_clear(self):
        floor = Floor(1, "F")
        floor.set_cell(5, 10, CellType.BOSS)
        floor.clear()
        assert floor.get_cell(5, 10).cell_type == CellType.EMPTY

    def test_count(self):
        floor = Floor(1, "F")
        floor.set_cell(0, 0, CellType.ENEMY)
        floor.set_cell(0, 1, CellType.ENEMY)
        floor.set_cell(0, 2, CellType.BOSS)
        assert floor.count(CellType.ENEMY) == 2
        assert floor.count(CellType.BOSS) == 1
        assert floor.count(CellType.WALL) == 0

    def test_find_cells(self):
        floor = Floor(1, "F")
        floor.set_cell(10, 20, CellType.TREASURE)
        floor.set_cell(30, 40, CellType.TREASURE)
        positions = floor.find_cells(CellType.TREASURE)
        assert (10, 20) in positions
        assert (30, 40) in positions
        assert len(positions) == 2

    def test_clone_is_deep(self):
        floor = Floor(1, "F")
        floor.set_cell(5, 5, CellType.TRAP)
        clone = floor.clone()
        clone.set_cell(5, 5, CellType.CAMP)
        assert floor.get_cell(5, 5).cell_type == CellType.TRAP

    def test_serialization_roundtrip(self):
        floor = Floor(2, "Étage 2")
        floor.set_cell(0, 0, CellType.WALL)
        floor.set_cell(HALF - 1, HALF, CellType.STAIRS_DOWN)
        d = floor.to_dict()
        assert d["id"] == 2
        assert d["name"] == "Étage 2"
        assert len(d["grid"]) == GRID_SIZE
        floor2 = Floor.from_dict(d)
        assert floor2.get_cell(0, 0).cell_type == CellType.WALL
        assert floor2.get_cell(HALF - 1, HALF).cell_type == CellType.STAIRS_DOWN


# ---------------------------------------------------------------------------
# GridModel — conversion de coordonnées
# ---------------------------------------------------------------------------

class TestCoordConversion(unittest.TestCase):

    def test_center_is_half_half(self):
        # (0, 0) → row = HALF-1-0 = 35, col = HALF+0 = 36
        row, col = GridModel.coords_to_index(0, 0)
        self.assertEqual(row, HALF - 1)
        self.assertEqual(col, HALF)

    def test_top_left_corner(self):
        # x=-36, y=35 → row=HALF-1-35=0, col=HALF-36=0
        row, col = GridModel.coords_to_index(-HALF, HALF - 1)
        self.assertEqual(row, 0)
        self.assertEqual(col, 0)

    def test_bottom_right_corner(self):
        # x=35, y=-36 → row=72, col=71... 
        # En fait x max = HALF-1 = 35, y min = -HALF = -36
        row, col = GridModel.coords_to_index(HALF - 1, -HALF)
        assert row == GRID_SIZE - 1
        assert col == GRID_SIZE - 1

    def test_inverse_roundtrip(self):
        for x in range(-HALF, HALF):
            for y in range(-HALF, HALF):
                row, col = GridModel.coords_to_index(x, y)
                x2, y2 = GridModel.index_to_coords(row, col)
                assert (x2, y2) == (x, y), f"Échec roundtrip pour ({x}, {y})"

    def test_out_of_bounds_raises(self):
        with self.assertRaises(ValueError):
            GridModel.coords_to_index(HALF, 0)   # x trop grand
        with self.assertRaises(ValueError):
            GridModel.coords_to_index(0, HALF)   # y trop grand
        with self.assertRaises(ValueError):
            GridModel.coords_to_index(-HALF - 1, 0)

    def test_is_valid_coords(self):
        assert GridModel.is_valid_coords(0, 0)
        assert GridModel.is_valid_coords(-HALF, -HALF)
        assert GridModel.is_valid_coords(HALF - 1, HALF - 1)
        assert not GridModel.is_valid_coords(HALF, 0)
        assert not GridModel.is_valid_coords(0, HALF)

    def test_is_valid_index(self):
        assert GridModel.is_valid_index(0, 0)
        assert GridModel.is_valid_index(GRID_SIZE - 1, GRID_SIZE - 1)
        assert not GridModel.is_valid_index(-1, 0)
        assert not GridModel.is_valid_index(GRID_SIZE, 0)


# ---------------------------------------------------------------------------
# GridModel — gestion des étages
# ---------------------------------------------------------------------------

class TestGridModel(unittest.TestCase):

    def test_starts_empty(self):
        m = GridModel()
        assert m.floor_count == 0
        assert m.get_active_floor() is None

    def test_add_floor(self):
        m = GridModel()
        f = m.add_floor("Niveau 1")
        assert m.floor_count == 1
        assert f.name == "Niveau 1"
        assert m.active_floor_id == f.floor_id

    def test_add_multiple_floors(self):
        m = GridModel()
        f1 = m.add_floor()
        f2 = m.add_floor()
        assert m.floor_count == 2
        assert f1.floor_id != f2.floor_id

    def test_remove_floor(self):
        m = GridModel()
        f = m.add_floor()
        m.remove_floor(f.floor_id)
        assert m.floor_count == 0

    def test_remove_nonexistent_floor_raises(self):
        m = GridModel()
        with self.assertRaises(ValueError):
            m.remove_floor(999)

    def test_set_active_floor(self):
        m = GridModel()
        m.add_floor()
        f2 = m.add_floor()
        m.set_active_floor(f2.floor_id)
        assert m.active_floor_id == f2.floor_id
        assert m.get_active_floor() is f2

    def test_set_active_invalid_raises(self):
        m = GridModel()
        with self.assertRaises(ValueError):
            m.set_active_floor(999)

    def test_clone_is_deep(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell(0, 0, CellType.BOSS)
        clone = m.clone()
        clone.get_active_floor().set_cell(0, 0, CellType.TRAP)
        assert m.get_active_floor().get_cell(0, 0).cell_type == CellType.BOSS

    def test_serialization_roundtrip(self):
        m = GridModel()
        f = m.add_floor("Étage A")
        f.set_cell(HALF - 1, HALF, CellType.STAIRS_DOWN)
        d = m.to_dict()
        assert d["version"] == 1
        m2 = GridModel.from_dict(d)
        assert m2.floor_count == 1
        assert m2.floors[0].name == "Étage A"
        assert m2.floors[0].get_cell(HALF - 1, HALF).cell_type == CellType.STAIRS_DOWN

    def test_clear_all(self):
        m = GridModel()
        m.add_floor()
        m.add_floor()
        m.clear_all()
        assert m.floor_count == 0
        assert m.active_floor_id == -1


# ---------------------------------------------------------------------------
# Lancer les tests directement
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()