"""
tests/test_serializer.py
Tests unitaires pour serialization/serializer.py  format Godot v2.

Format attendu :
{
  "level": int,
  "width": 72, "height": 72, "centerX": 36, "centerY": 36,
  "cells": [
    { "pos": [x, y] },                                          # GROUND implicite
    { "pos": [x, y], "type": "camp" },                          # autre type
    { "pos": [x, y], "type": "wall", "mask": int, "rot_y": float }  # WALL
  ]
}
"""

import sys
import os
import json
import tempfile
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.grid import Cell, CellType, GridModel, GRID_SIZE, HALF
from serialization.serializer import Serializer, SerializerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_model() -> GridModel:
    """Modèle minimal avec STAIRS_DOWN en (0,0) et WALL en coin."""
    m = GridModel()
    f = m.add_floor("Test")
    f.set_cell(HALF - 1, HALF, CellType.STAIRS_DOWN)
    f.set_cell(0, 0, CellType.WALL)
    return m


def make_godot_json(cells: list, level: int = 1) -> str:
    """Construit un JSON Godot v2 minimal valide."""
    return json.dumps({
        "level":   level,
        "width":   GRID_SIZE,
        "height":  GRID_SIZE,
        "centerX": HALF,
        "centerY": HALF,
        "cells":   cells,
    })


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.s = Serializer()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_to_json_string_produces_valid_json(self):
        raw = self.s.to_json_string(make_model())
        data = json.loads(raw)
        self.assertIn("level", data)
        self.assertIn("cells", data)
        self.assertIsInstance(data["cells"], list)

    def test_to_json_string_empty_model_raises(self):
        with self.assertRaises(SerializerError):
            self.s.to_json_string(GridModel())

    def test_save_creates_file(self):
        out = self.tmp / "level.json"
        self.s.save(make_model(), out)
        self.assertTrue(out.exists())

    def test_save_file_is_valid_json(self):
        out = self.tmp / "level.json"
        self.s.save(make_model(), out)
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("level", data)
        self.assertIn("cells", data)

    def test_save_empty_model_raises(self):
        with self.assertRaises(SerializerError):
            self.s.save(GridModel(), self.tmp / "empty.json")

    def test_save_creates_parent_dirs(self):
        out = self.tmp / "sub" / "deep" / "level.json"
        self.s.save(make_model(), out)
        self.assertTrue(out.exists())

    def test_cells_is_sparse_no_empty(self):
        raw = self.s.to_json_string(make_model())
        data = json.loads(raw)
        types_in_cells = [c.get("type", "ground") for c in data["cells"]]
        self.assertNotIn("empty", types_in_cells)

    def test_ground_has_no_type_field(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 0, CellType.GROUND)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        ground_cells = [c for c in data["cells"] if "type" not in c]
        self.assertEqual(len(ground_cells), 1)
        self.assertEqual(ground_cells[0]["pos"], [0, 0])

    def test_pos_uses_centered_coords(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell(HALF - 1, HALF, CellType.STAIRS_DOWN)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        positions = [c["pos"] for c in data["cells"]]
        self.assertIn([0, 0], positions)

    def test_wall_has_mask_and_rot_y(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 0, CellType.WALL)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        wall_cells = [c for c in data["cells"] if c.get("type") == "wall"]
        self.assertEqual(len(wall_cells), 1)
        w = wall_cells[0]
        self.assertIn("mask", w)
        self.assertIn("rot_y", w)
        self.assertIsInstance(w["mask"], int)
        self.assertIsInstance(w["rot_y"], float)

    def test_non_wall_has_no_mask_nor_rot_y(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(1, 0, CellType.CAMP)
        f.set_cell_at(2, 0, CellType.STAIRS_DOWN)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        for c in data["cells"]:
            if c.get("type") not in ("wall",):
                self.assertNotIn("mask", c)
                self.assertNotIn("rot_y", c)

    def test_type_uses_underscores(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 0, CellType.STAIRS_DOWN)
        f.set_cell_at(1, 0, CellType.STAIRS_UP)
        raw = self.s.to_json_string(m)
        self.assertIn("stairs_down", raw)
        self.assertIn("stairs_up", raw)
        self.assertNotIn("stairs-down", raw)
        self.assertNotIn("stairs-up", raw)

    def test_wall_mask_isolated(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 0, CellType.WALL)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        w = next(c for c in data["cells"] if c.get("type") == "wall")
        self.assertEqual(w["mask"], 0)
        self.assertEqual(w["rot_y"], 0.0)

    def test_wall_mask_north_south_corridor(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 1, CellType.GROUND)
        f.set_cell_at(0, 0, CellType.WALL)
        f.set_cell_at(0, -1, CellType.GROUND)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        w = next(c for c in data["cells"] if c.get("type") == "wall")
        self.assertEqual(w["mask"], 5)
        self.assertEqual(w["rot_y"], 0.0)

    def test_wall_mask_east_west_corridor(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(1, 0, CellType.GROUND)
        f.set_cell_at(0, 0, CellType.WALL)
        f.set_cell_at(-1, 0, CellType.GROUND)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        w = next(c for c in data["cells"] if c.get("type") == "wall")
        self.assertEqual(w["mask"], 10)
        self.assertEqual(w["rot_y"], 90.0)

    def test_wall_mask_full_cross(self):
        m = GridModel()
        f = m.add_floor()
        f.set_cell_at(0, 1, CellType.GROUND)
        f.set_cell_at(1, 0, CellType.GROUND)
        f.set_cell_at(0, -1, CellType.GROUND)
        f.set_cell_at(-1, 0, CellType.GROUND)
        f.set_cell_at(0, 0, CellType.WALL)
        raw = self.s.to_json_string(m)
        data = json.loads(raw)
        w = next(c for c in data["cells"] if c.get("type") == "wall")
        self.assertEqual(w["mask"], 15)
        self.assertEqual(w["rot_y"], 0.0)

    def test_save_all_creates_one_file_per_floor(self):
        m = GridModel()
        m.add_floor("Étage 1")
        m.add_floor("Étage 2")
        m.add_floor("Étage 3")
        paths = self.s.save_all(m, self.tmp / "export")
        self.assertEqual(len(paths), 3)
        for p in paths:
            self.assertTrue(p.exists())


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class TestImport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.s = Serializer()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_roundtrip_save_load(self):
        m = make_model()
        out = self.tmp / "level.json"
        self.s.save(m, out)
        m2 = self.s.load(out)
        self.assertEqual(m2.floor_count, 1)
        self.assertEqual(
            m2.floors[0].get_cell(HALF - 1, HALF).cell_type,
            CellType.STAIRS_DOWN,
        )
        self.assertEqual(
            m2.floors[0].get_cell(0, 0).cell_type,
            CellType.WALL,
        )

    def test_load_nonexistent_file_raises(self):
        with self.assertRaises(SerializerError):
            self.s.load(self.tmp / "does_not_exist.json")

    def test_load_malformed_json_raises(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(SerializerError):
            self.s.load(bad)

    def test_missing_cells_key_raises(self):
        with self.assertRaises(SerializerError):
            self.s.from_json_string(json.dumps({"level": 1}))

    def test_cells_not_a_list_raises(self):
        bad = json.dumps({"level": 1, "cells": {"0,0": {"pos": [0, 0]}}})
        with self.assertRaises(SerializerError):
            self.s.from_json_string(bad)

    def test_unknown_cell_type_raises(self):
        bad = make_godot_json([{"pos": [0, 0], "type": "unknown_xyz"}])
        with self.assertRaises(SerializerError):
            self.s.from_json_string(bad)

    def test_invalid_pos_raises(self):
        bad = make_godot_json([{"pos": "not_a_list"}])
        with self.assertRaises(SerializerError):
            self.s.from_json_string(bad)

    def test_out_of_bounds_pos_raises(self):
        bad = make_godot_json([{"pos": [999, 999]}])
        with self.assertRaises(SerializerError):
            self.s.from_json_string(bad)

    def test_absent_type_defaults_to_ground(self):
        raw = make_godot_json([{"pos": [0, 0]}])
        m = self.s.from_json_string(raw)
        self.assertEqual(m.floors[0].get_cell_at(0, 0).cell_type, CellType.GROUND)

    def test_mask_and_rot_y_ignored_on_import(self):
        raw = make_godot_json([
            {"pos": [0, 0], "type": "wall", "mask": 5, "rot_y": 0.0}
        ])
        m = self.s.from_json_string(raw)
        self.assertEqual(m.floors[0].get_cell_at(0, 0).cell_type, CellType.WALL)

    def test_all_cell_types_roundtrip(self):
        m = GridModel()
        f = m.add_floor("AllTypes")
        col = 0
        for ct in CellType:
            if ct == CellType.EMPTY:
                continue
            f.set_cell_at(col, 0, ct)
            col += 1
        out = self.tmp / "all_types.json"
        self.s.save(m, out)
        m2 = self.s.load(out)
        col = 0
        for ct in CellType:
            if ct == CellType.EMPTY:
                continue
            self.assertEqual(m2.floors[0].get_cell_at(col, 0).cell_type, ct)
            col += 1

    def test_stairs_down_underscore_import(self):
        raw = make_godot_json([{"pos": [0, 0], "type": "stairs_down"}])
        m = self.s.from_json_string(raw)
        self.assertEqual(m.floors[0].get_cell_at(0, 0).cell_type, CellType.STAIRS_DOWN)

    def test_stairs_up_underscore_import(self):
        raw = make_godot_json([{"pos": [0, 0], "type": "stairs_up"}])
        m = self.s.from_json_string(raw)
        self.assertEqual(m.floors[0].get_cell_at(0, 0).cell_type, CellType.STAIRS_UP)

    def test_multiple_cells_all_imported(self):
        raw = make_godot_json([
            {"pos": [0, 0]},
            {"pos": [1, 0], "type": "camp"},
            {"pos": [-1, 0], "type": "enemy"},
        ])
        m = self.s.from_json_string(raw)
        f = m.floors[0]
        self.assertEqual(f.get_cell_at(0, 0).cell_type, CellType.GROUND)
        self.assertEqual(f.get_cell_at(1, 0).cell_type, CellType.CAMP)
        self.assertEqual(f.get_cell_at(-1, 0).cell_type, CellType.ENEMY)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

class TestPaths(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_make_relative(self):
        s = Serializer(base_dir=self.tmp)
        abs_path = str(self.tmp / "sprites" / "hero.png")
        rel = s.make_relative(abs_path)
        self.assertEqual(rel, os.path.join("sprites", "hero.png"))

    def test_resolve(self):
        s = Serializer(base_dir=self.tmp)
        resolved = s.resolve("sprites/hero.png")
        self.assertEqual(resolved, self.tmp / "sprites" / "hero.png")


if __name__ == "__main__":
    unittest.main()