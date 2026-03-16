"""
tests/test_serializer.py
Tests unitaires pour serialization/serializer.py
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


def make_model() -> GridModel:
    m = GridModel()
    f = m.add_floor("Test")
    f.set_cell(HALF - 1, HALF, CellType.STAIRS_DOWN)
    f.set_cell(0, 0, CellType.WALL)
    return m


class TestExport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_to_json_string_produces_valid_json(self):
        s = Serializer()
        raw = s.to_json_string(make_model())
        data = json.loads(raw)
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["floors"]), 1)

    def test_to_json_string_empty_model_raises(self):
        s = Serializer()
        with self.assertRaises(SerializerError):
            s.to_json_string(GridModel())

    def test_save_creates_file(self):
        s = Serializer()
        out = self.tmp / "project.json"
        s.save(make_model(), out)
        self.assertTrue(out.exists())

    def test_save_file_is_valid_json(self):
        s = Serializer()
        out = self.tmp / "project.json"
        s.save(make_model(), out)
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["version"], 1)

    def test_save_empty_model_raises(self):
        s = Serializer()
        with self.assertRaises(SerializerError):
            s.save(GridModel(), self.tmp / "empty.json")

    def test_save_creates_parent_dirs(self):
        s = Serializer()
        out = self.tmp / "sub" / "deep" / "project.json"
        s.save(make_model(), out)
        self.assertTrue(out.exists())


class TestImport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_roundtrip_save_load(self):
        s = Serializer()
        m = make_model()
        out = self.tmp / "project.json"
        s.save(m, out)
        m2 = s.load(out)
        self.assertEqual(m2.floor_count, 1)
        self.assertEqual(m2.floors[0].name, "Test")
        self.assertEqual(m2.floors[0].get_cell(HALF - 1, HALF).cell_type, CellType.STAIRS_DOWN)
        self.assertEqual(m2.floors[0].get_cell(0, 0).cell_type, CellType.WALL)

    def test_load_nonexistent_file_raises(self):
        s = Serializer()
        with self.assertRaises(SerializerError):
            s.load(self.tmp / "does_not_exist.json")

    def test_load_malformed_json_raises(self):
        s = Serializer()
        bad = self.tmp / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(SerializerError):
            s.load(bad)

    def test_wrong_version_raises(self):
        s = Serializer()
        m = GridModel()
        m.add_floor()
        data = m.to_dict()
        data["version"] = 99
        with self.assertRaises(SerializerError):
            s.from_json_string(json.dumps(data))

    def test_missing_floors_key_raises(self):
        s = Serializer()
        with self.assertRaises(SerializerError):
            s.from_json_string(json.dumps({"version": 1}))

    def test_empty_floors_raises(self):
        s = Serializer()
        with self.assertRaises(SerializerError):
            s.from_json_string(json.dumps({"version": 1, "floors": []}))

    def test_wrong_grid_size_raises(self):
        s = Serializer()
        m = GridModel()
        m.add_floor()
        data = m.to_dict()
        data["floors"][0]["grid"] = data["floors"][0]["grid"][:10]
        with self.assertRaises(SerializerError):
            s.from_json_string(json.dumps(data))

    def test_unknown_cell_type_raises(self):
        s = Serializer()
        m = GridModel()
        m.add_floor()
        data = m.to_dict()
        data["floors"][0]["grid"][0][0]["type"] = "unknown_xyz"
        with self.assertRaises(SerializerError):
            s.from_json_string(json.dumps(data))

    def test_custom_image_preserved(self):
        s = Serializer()
        m = GridModel()
        f = m.add_floor()
        f.set_cell(5, 5, CellType.BOSS, custom_image="sprites/boss.png")
        out = self.tmp / "sprites.json"
        s.save(m, out)
        m2 = s.load(out)
        self.assertEqual(m2.floors[0].get_cell(5, 5).custom_image, "sprites/boss.png")

    def test_multiple_floors_roundtrip(self):
        s = Serializer()
        m = GridModel()
        m.add_floor("Étage 1")
        m.add_floor("Étage 2")
        m.add_floor("Boss Floor")
        out = self.tmp / "multi.json"
        s.save(m, out)
        m2 = s.load(out)
        self.assertEqual(m2.floor_count, 3)
        names = [f.name for f in m2.floors]
        self.assertIn("Étage 1", names)
        self.assertIn("Boss Floor", names)

    def test_all_cell_types_roundtrip(self):
        s = Serializer()
        m = GridModel()
        f = m.add_floor("AllTypes")
        for i, ct in enumerate(CellType):
            f.set_cell(i % GRID_SIZE, (i * 3) % GRID_SIZE, ct)
        out = self.tmp / "all_types.json"
        s.save(m, out)
        m2 = s.load(out)
        for i, ct in enumerate(CellType):
            self.assertEqual(
                m2.floors[0].get_cell(i % GRID_SIZE, (i * 3) % GRID_SIZE).cell_type, ct
            )


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