"""
tests/test_generator.py
Tests unitaires pour core/generator.py

Lance avec :
    python -m unittest tests/test_generator.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.grid import CellType, Floor, GridModel, GRID_SIZE
from core.generator import Generator, GenerationReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_floor() -> Floor:
    return Floor(floor_id=1, name="Test")


def fill_rect_coords(floor: Floor, x1: int, y1: int,
                     x2: int, y2: int) -> None:
    """Remplit un rectangle GROUND en coordonnees centrees."""
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            floor.set_cell_at(x, y, CellType.GROUND)


def count_type(floor: Floor, ct: CellType) -> int:
    """Compte les cellules d'un type donne."""
    return sum(
        1
        for r in range(GRID_SIZE)
        for c in range(GRID_SIZE)
        if floor.grid[r][c].cell_type == ct
    )


# ---------------------------------------------------------------------------
# Tests GenerationReport
# ---------------------------------------------------------------------------

class TestGenerationReport(unittest.TestCase):

    def test_summary_contient_champs(self):
        report = GenerationReport(
            rooms_found=3,
            rooms_kept=2,
            rooms_discarded=1,
            corridors_traced=2,
            transitions_added=1,
            walls_placed=42,
            stairs_down_set=True,
        )
        s = report.summary()
        self.assertIn("3", s)
        self.assertIn("2", s)
        self.assertIn("42", s)
        self.assertIn("OK", s)

    def test_summary_echec_stairs(self):
        report = GenerationReport(stairs_down_set=False)
        self.assertIn("ECHEC", report.summary())

    def test_summary_avec_warnings(self):
        report = GenerationReport(warnings=["Alerte test"])
        self.assertIn("Alerte test", report.summary())

    def test_valeurs_defaut(self):
        report = GenerationReport()
        self.assertEqual(report.rooms_found, 0)
        self.assertEqual(report.warnings, [])


# ---------------------------------------------------------------------------
# Tests Generator.run -- grille vide
# ---------------------------------------------------------------------------

class TestGeneratorEmptyFloor(unittest.TestCase):

    def test_grille_vide_retourne_report(self):
        """Grille sans GROUND -> rapport avec avertissement, pas de crash."""
        floor = make_floor()
        gen = Generator(seed=0)
        report = gen.run(floor)
        self.assertEqual(report.rooms_kept, 0)
        self.assertTrue(len(report.warnings) > 0)

    def test_grille_vide_stairs_down_pas_pose(self):
        """Sur grille vide, aucune salle -> run() s'arrete tot, STAIRS_DOWN non pose."""
        floor = make_floor()
        gen = Generator(seed=0)
        report = gen.run(floor)
        # Le generateur s'arrete avant _place_stairs_down quand il n'y a aucune salle
        self.assertEqual(report.rooms_kept, 0)
        self.assertGreater(len(report.warnings), 0)
        row, col = GridModel.coords_to_index(0, 0)
        # La case (0,0) reste EMPTY (aucune salle, pas de generation)
        self.assertEqual(floor.grid[row][col].cell_type, CellType.EMPTY)


# ---------------------------------------------------------------------------
# Tests Generator.run -- une salle
# ---------------------------------------------------------------------------

class TestGeneratorOneRoom(unittest.TestCase):

    def setUp(self):
        self.floor = make_floor()
        # Salle 5x5 centree autour de (0,0)
        fill_rect_coords(self.floor, -2, -2, 2, 2)
        self.gen = Generator(seed=42)
        self.report = self.gen.run(self.floor)

    def test_une_salle_detectee(self):
        self.assertGreaterEqual(self.report.rooms_kept, 1)

    def test_stairs_down_force(self):
        """STAIRS_DOWN doit etre a (0,0)."""
        row, col = GridModel.coords_to_index(0, 0)
        self.assertEqual(
            self.floor.grid[row][col].cell_type, CellType.STAIRS_DOWN
        )
        self.assertTrue(self.report.stairs_down_set)

    def test_murs_poses(self):
        """Des murs doivent entourer la salle."""
        self.assertGreater(self.report.walls_placed, 0)
        self.assertGreater(count_type(self.floor, CellType.WALL), 0)

    def test_aucun_couloir_une_salle(self):
        """Une seule salle -> aucun couloir a tracer."""
        self.assertEqual(self.report.corridors_traced, 0)


# ---------------------------------------------------------------------------
# Tests Generator.run -- deux salles
# ---------------------------------------------------------------------------

class TestGeneratorTwoRooms(unittest.TestCase):

    def setUp(self):
        self.floor = make_floor()
        # Salle A : coin superieur gauche
        fill_rect_coords(self.floor, -20, 10, -15, 15)
        # Salle B : coin inferieur droit
        fill_rect_coords(self.floor, 10, -20, 15, -15)
        self.gen = Generator(seed=7)
        self.report = self.gen.run(self.floor)

    def test_deux_salles_detectees(self):
        self.assertEqual(self.report.rooms_kept, 2)

    def test_au_moins_un_couloir(self):
        """Deux salles -> au moins 1 couloir trace."""
        self.assertGreaterEqual(self.report.corridors_traced, 1)

    def test_stairs_down_pose(self):
        self.assertTrue(self.report.stairs_down_set)

    def test_murs_presents(self):
        self.assertGreater(count_type(self.floor, CellType.WALL), 0)

    def test_ground_present_entre_salles(self):
        """Des cellules GROUND existent (couloir trace)."""
        self.assertGreater(count_type(self.floor, CellType.GROUND), 0)


# ---------------------------------------------------------------------------
# Tests Generator.run -- STAIRS_DOWN force a (0,0)
# ---------------------------------------------------------------------------

class TestStairsDown(unittest.TestCase):

    def test_stairs_down_ecrase_ground(self):
        """STAIRS_DOWN ecrase un GROUND existant en (0,0)."""
        floor = make_floor()
        fill_rect_coords(floor, -3, -3, 3, 3)
        gen = Generator(seed=0)
        gen.run(floor)
        row, col = GridModel.coords_to_index(0, 0)
        self.assertEqual(floor.grid[row][col].cell_type, CellType.STAIRS_DOWN)

    def test_stairs_down_ecrase_wall(self):
        """STAIRS_DOWN ecrase un WALL existant en (0,0)."""
        floor = make_floor()
        # Une salle a cote de (0,0) pour que (0,0) devienne un mur
        fill_rect_coords(floor, 1, 1, 5, 5)
        gen = Generator(seed=0)
        gen.run(floor)
        row, col = GridModel.coords_to_index(0, 0)
        self.assertEqual(floor.grid[row][col].cell_type, CellType.STAIRS_DOWN)

    def test_stairs_down_unique(self):
        """Il y a exactement une cellule STAIRS_DOWN apres generation."""
        floor = make_floor()
        fill_rect_coords(floor, -5, -5, 5, 5)
        gen = Generator(seed=0)
        gen.run(floor)
        self.assertEqual(count_type(floor, CellType.STAIRS_DOWN), 1)


# ---------------------------------------------------------------------------
# Tests Generator.run -- STAIRS_UP
# ---------------------------------------------------------------------------

class TestStairsUp(unittest.TestCase):

    def test_stairs_up_connecte(self):
        """STAIRS_UP dans une salle isolee -> un couloir supplementaire trace."""
        floor = make_floor()
        # Salle normale
        fill_rect_coords(floor, -5, -5, -2, -2)
        # Salle STAIRS_UP eloignee
        fill_rect_coords(floor, 10, 10, 13, 13)
        floor.set_cell_at(11, 11, CellType.STAIRS_UP)

        gen = Generator(seed=3)
        report_before = 0
        report = gen.run(floor)
        # Au moins 1 couloir pour relier les deux salles
        self.assertGreaterEqual(report.corridors_traced, 1)

    def test_sans_stairs_up(self):
        """Sans STAIRS_UP, pas d'erreur."""
        floor = make_floor()
        fill_rect_coords(floor, -5, -5, 5, 5)
        gen = Generator(seed=0)
        report = gen.run(floor)
        self.assertTrue(report.stairs_down_set)


# ---------------------------------------------------------------------------
# Tests Generator.run -- murs
# ---------------------------------------------------------------------------

class TestWalls(unittest.TestCase):

    def test_murs_entourent_ground(self):
        """Chaque cellule WALL est adjacente a au moins une cellule non-EMPTY."""
        floor = make_floor()
        fill_rect_coords(floor, -5, -5, 5, 5)
        gen = Generator(seed=0)
        gen.run(floor)

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if floor.grid[r][c].cell_type != CellType.WALL:
                    continue
                # Verifie qu au moins un voisin est non-EMPTY
                has_solid_neighbor = False
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE):
                        continue
                    if floor.grid[nr][nc].cell_type != CellType.EMPTY:
                        has_solid_neighbor = True
                        break
                self.assertTrue(
                    has_solid_neighbor,
                    f"Mur isole en ({r}, {c})"
                )

    def test_aucun_mur_sur_ground(self):
        """Aucune cellule GROUND ne doit etre convertie en WALL."""
        floor = make_floor()
        fill_rect_coords(floor, -3, -3, 3, 3)
        # Memorise les positions GROUND avant generation
        ground_before = {
            (r, c)
            for r in range(GRID_SIZE)
            for c in range(GRID_SIZE)
            if floor.grid[r][c].cell_type == CellType.GROUND
        }
        gen = Generator(seed=0)
        gen.run(floor)
        # Aucune position qui etait GROUND ne doit devenir WALL
        for r, c in ground_before:
            ct = floor.grid[r][c].cell_type
            self.assertNotEqual(
                ct, CellType.WALL,
                f"Case ({r},{c}) etait GROUND et est devenue WALL"
            )


# ---------------------------------------------------------------------------
# Tests Generator -- reproductibilite
# ---------------------------------------------------------------------------

class TestGeneratorReproductibility(unittest.TestCase):

    def _run_and_snapshot(self, seed: int) -> dict:
        """Lance le generateur et retourne un snapshot de la grille."""
        floor = make_floor()
        fill_rect_coords(floor, -10, -10, -5, -5)
        fill_rect_coords(floor, 5, 5, 10, 10)
        gen = Generator(seed=seed)
        gen.run(floor)
        return {
            (r, c): floor.grid[r][c].cell_type
            for r in range(GRID_SIZE)
            for c in range(GRID_SIZE)
            if floor.grid[r][c].cell_type != CellType.EMPTY
        }

    def test_meme_seed_meme_resultat(self):
        """Deux runs avec la meme seed produisent exactement le meme resultat."""
        snap1 = self._run_and_snapshot(seed=123)
        snap2 = self._run_and_snapshot(seed=123)
        self.assertEqual(snap1, snap2)

    def test_seeds_differentes_resultats_differents(self):
        """Deux seeds differentes produisent generalement des resultats differents."""
        snap1 = self._run_and_snapshot(seed=1)
        snap2 = self._run_and_snapshot(seed=999)
        # Pas garanti mais tres probable avec deux salles et des couloirs en L
        self.assertNotEqual(snap1, snap2)


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
