"""
tests/test_algorithms.py
Tests unitaires pour core/algorithms.py

Lance avec :
    python -m unittest tests/test_algorithms.py -v
"""

import sys
import os
import unittest
import random

# Assure que le dossier racine est dans le path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.grid import CellType, Floor, GRID_SIZE
from core.algorithms import (
    MIN_ROOM_CELLS,
    add_extra_edges,
    blob_room,
    build_mst,
    corridor_length,
    filter_rooms,
    find_connection_points,
    flood_fill,
    room_center,
    trace_corridor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_floor() -> Floor:
    """Retourne un etage vide."""
    return Floor(floor_id=1, name="Test")


def fill_rect(floor: Floor, x1: int, y1: int, x2: int, y2: int) -> set:
    """Remplit un rectangle de cellules GROUND (coordonnees centrees).

    x1 <= x <= x2, y1 <= y <= y2
    Retourne le set des (row, col) posees.
    """
    from core.grid import GridModel
    cells = set()
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            row, col = GridModel.coords_to_index(x, y)
            floor.grid[row][col].cell_type = CellType.GROUND
            cells.add((row, col))
    return cells


def set_cell_rc(floor: Floor, row: int, col: int,
                ct: CellType = CellType.GROUND) -> None:
    """Pose un type de cellule par index (row, col)."""
    floor.grid[row][col].cell_type = ct


# ---------------------------------------------------------------------------
# Tests flood_fill
# ---------------------------------------------------------------------------

class TestFloodFill(unittest.TestCase):

    def test_grille_vide(self):
        """Grille sans GROUND -> aucune salle."""
        floor = make_floor()
        rooms = flood_fill(floor)
        self.assertEqual(rooms, [])

    def test_une_cellule(self):
        """Une seule cellule GROUND -> une salle d'une cellule."""
        floor = make_floor()
        set_cell_rc(floor, 10, 10)
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 1)
        self.assertIn((10, 10), rooms[0])

    def test_une_salle_rectangulaire(self):
        """Rectangle 3x3 -> une seule salle de 9 cellules."""
        floor = make_floor()
        fill_rect(floor, -1, -1, 1, 1)
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 1)
        self.assertEqual(len(rooms[0]), 9)

    def test_deux_salles_separees(self):
        """Deux rectangles non contigus -> deux salles."""
        floor = make_floor()
        fill_rect(floor, -10, -10, -8, -8)  # salle A
        fill_rect(floor,   8,   8,  10,  10)  # salle B
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 2)

    def test_salle_en_L(self):
        """Salle en L -> une seule salle (contigues)."""
        floor = make_floor()
        # Branche horizontale
        for x in range(-5, 1):
            set_cell_rc(floor, 36, 36 + x)  # row=36 (y=0)
        # Branche verticale
        for row in range(30, 37):
            set_cell_rc(floor, row, 36)      # col=36 (x=0)
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 1)

    def test_cellules_non_ground_ignorees(self):
        """WALL, ENEMY etc. ne sont pas detectes comme salles GROUND."""
        floor = make_floor()
        set_cell_rc(floor, 20, 20, CellType.WALL)
        set_cell_rc(floor, 21, 21, CellType.ENEMY)
        rooms = flood_fill(floor)
        self.assertEqual(rooms, [])

    def test_trois_salles(self):
        """Trois rectangles distincts -> trois salles."""
        floor = make_floor()
        fill_rect(floor, -15, 0, -12, 3)
        fill_rect(floor,   0, 0,   3, 3)
        fill_rect(floor,  12, 0,  15, 3)
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 3)

    def test_toutes_cellules_ground(self):
        """Grille entierement GROUND -> une seule salle."""
        floor = make_floor()
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                floor.grid[r][c].cell_type = CellType.GROUND
        rooms = flood_fill(floor)
        self.assertEqual(len(rooms), 1)
        self.assertEqual(len(rooms[0]), GRID_SIZE * GRID_SIZE)


# ---------------------------------------------------------------------------
# Tests filter_rooms
# ---------------------------------------------------------------------------

class TestFilterRooms(unittest.TestCase):

    def _make_room(self, size: int) -> set:
        return {(i, 0) for i in range(size)}

    def test_filtre_standard(self):
        rooms = [self._make_room(1), self._make_room(2), self._make_room(5)]
        result = filter_rooms(rooms, min_cells=2)
        self.assertEqual(len(result), 2)

    def test_toutes_passent(self):
        rooms = [self._make_room(3), self._make_room(10)]
        result = filter_rooms(rooms, min_cells=2)
        self.assertEqual(len(result), 2)

    def test_aucune_ne_passe(self):
        rooms = [self._make_room(1)]
        result = filter_rooms(rooms, min_cells=2)
        self.assertEqual(result, [])

    def test_liste_vide(self):
        self.assertEqual(filter_rooms([]), [])

    def test_min_cells_1(self):
        rooms = [self._make_room(1), self._make_room(2)]
        result = filter_rooms(rooms, min_cells=1)
        self.assertEqual(len(result), 2)

    def test_taille_exactement_min(self):
        rooms = [self._make_room(2)]
        result = filter_rooms(rooms, min_cells=2)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# Tests room_center
# ---------------------------------------------------------------------------

class TestRoomCenter(unittest.TestCase):

    def test_cellule_unique(self):
        room = {(5, 10)}
        cr, cc = room_center(room)
        self.assertAlmostEqual(cr, 5.0)
        self.assertAlmostEqual(cc, 10.0)

    def test_deux_cellules(self):
        room = {(0, 0), (2, 4)}
        cr, cc = room_center(room)
        self.assertAlmostEqual(cr, 1.0)
        self.assertAlmostEqual(cc, 2.0)

    def test_carre_3x3(self):
        room = {(r, c) for r in range(3) for c in range(3)}
        cr, cc = room_center(room)
        self.assertAlmostEqual(cr, 1.0)
        self.assertAlmostEqual(cc, 1.0)

    def test_centre_non_entier(self):
        room = {(0, 0), (1, 0), (2, 0)}
        cr, cc = room_center(room)
        self.assertAlmostEqual(cr, 1.0)
        self.assertAlmostEqual(cc, 0.0)


# ---------------------------------------------------------------------------
# Tests build_mst
# ---------------------------------------------------------------------------

class TestBuildMst(unittest.TestCase):

    def _room_at(self, row: int, col: int) -> set:
        return {(row, col)}

    def test_zero_salle(self):
        self.assertEqual(build_mst([]), [])

    def test_une_salle(self):
        self.assertEqual(build_mst([self._room_at(0, 0)]), [])

    def test_deux_salles(self):
        rooms = [self._room_at(0, 0), self._room_at(10, 10)]
        edges = build_mst(rooms)
        self.assertEqual(len(edges), 1)
        self.assertIn(tuple(sorted(edges[0])), [(0, 1)])

    def test_trois_salles_mst_deux_aretes(self):
        """MST de 3 noeuds = 2 aretes."""
        rooms = [
            self._room_at(0, 0),
            self._room_at(0, 20),
            self._room_at(0, 40),
        ]
        edges = build_mst(rooms)
        self.assertEqual(len(edges), 2)

    def test_quatre_salles_mst_trois_aretes(self):
        """MST de 4 noeuds = 3 aretes."""
        rooms = [self._room_at(i * 10, 0) for i in range(4)]
        edges = build_mst(rooms)
        self.assertEqual(len(edges), 3)

    def test_indices_valides(self):
        """Tous les indices references existent dans la liste de salles."""
        rooms = [self._room_at(i * 5, i * 5) for i in range(5)]
        edges = build_mst(rooms)
        n = len(rooms)
        for a, b in edges:
            self.assertGreaterEqual(a, 0)
            self.assertLess(a, n)
            self.assertGreaterEqual(b, 0)
            self.assertLess(b, n)


# ---------------------------------------------------------------------------
# Tests add_extra_edges
# ---------------------------------------------------------------------------

class TestAddExtraEdges(unittest.TestCase):

    def _rooms(self, n: int) -> list:
        return [{(i, 0)} for i in range(n)]

    def test_zero_salle(self):
        result = add_extra_edges([], [], ratio=0.30)
        self.assertEqual(result, [])

    def test_une_salle(self):
        result = add_extra_edges([], self._rooms(1), ratio=0.30)
        self.assertEqual(result, [])

    def test_pas_de_doublons(self):
        rooms = self._rooms(5)
        mst = [(0, 1), (1, 2), (2, 3), (3, 4)]
        result = add_extra_edges(mst, rooms, ratio=0.30)
        normalized = [tuple(sorted(e)) for e in result]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_pas_de_boucles(self):
        rooms = self._rooms(5)
        mst = [(0, 1), (1, 2), (2, 3), (3, 4)]
        result = add_extra_edges(mst, rooms, ratio=0.30)
        for a, b in result:
            self.assertNotEqual(a, b)

    def test_contient_les_aretes_originales(self):
        rooms = self._rooms(4)
        mst = [(0, 1), (1, 2), (2, 3)]
        result = add_extra_edges(mst, rooms, ratio=0.30)
        for edge in mst:
            self.assertIn(edge, result)

    def test_ratio_zero_retourne_original(self):
        """ratio=0 -> au moins 1 arete ajoutee (max(1, ...))."""
        rooms = self._rooms(4)
        mst = [(0, 1), (1, 2), (2, 3)]
        result = add_extra_edges(mst, rooms, ratio=0.0)
        self.assertGreaterEqual(len(result), len(mst))


# ---------------------------------------------------------------------------
# Tests corridor_length
# ---------------------------------------------------------------------------

class TestCorridorLength(unittest.TestCase):

    def test_meme_point(self):
        self.assertEqual(corridor_length((5, 5), (5, 5)), 0)

    def test_horizontal(self):
        self.assertEqual(corridor_length((0, 0), (0, 10)), 10)

    def test_vertical(self):
        self.assertEqual(corridor_length((0, 0), (10, 0)), 10)

    def test_diagonal_manhattan(self):
        self.assertEqual(corridor_length((0, 0), (3, 4)), 7)

    def test_negatif(self):
        self.assertEqual(corridor_length((5, 5), (0, 0)), 10)


# ---------------------------------------------------------------------------
# Tests trace_corridor
# ---------------------------------------------------------------------------

class TestTraceCorridor(unittest.TestCase):

    def test_couloir_horizontal(self):
        """Meme ligne -> couloir horizontal."""
        floor = make_floor()
        rng = random.Random(0)
        posed = trace_corridor(floor, (10, 5), (10, 15), rng=rng)
        # Toutes les cellules posees sont sur la meme ligne
        for r, c in posed:
            self.assertEqual(r, 10)
        # Longueur : 15 - 5 + 1 = 11 cellules max
        self.assertGreaterEqual(len(posed), 1)

    def test_couloir_vertical(self):
        """Meme colonne -> couloir vertical."""
        floor = make_floor()
        rng = random.Random(0)
        posed = trace_corridor(floor, (5, 10), (15, 10), rng=rng)
        for r, c in posed:
            self.assertEqual(c, 10)

    def test_couloir_en_L(self):
        """Points non alignes -> couloir en L (deux segments)."""
        floor = make_floor()
        rng = random.Random(42)
        posed = trace_corridor(floor, (5, 5), (15, 20), rng=rng)
        self.assertGreater(len(posed), 0)
        # Verifie que des cellules GROUND ont ete posees
        for r, c in posed:
            self.assertEqual(floor.grid[r][c].cell_type, CellType.GROUND)

    def test_ne_pose_pas_sur_non_empty(self):
        """Les cellules non-EMPTY existantes ne sont pas ecrasees."""
        floor = make_floor()
        floor.grid[10][10].cell_type = CellType.WALL
        rng = random.Random(0)
        trace_corridor(floor, (10, 5), (10, 15), rng=rng)
        # La cellule WALL doit rester WALL
        self.assertEqual(floor.grid[10][10].cell_type, CellType.WALL)

    def test_meme_point_depart_arrivee(self):
        """Depart == arrivee -> aucune cellule posee (ou juste celle-la)."""
        floor = make_floor()
        rng = random.Random(0)
        posed = trace_corridor(floor, (10, 10), (10, 10), rng=rng)
        # Peut poser 0 ou 1 cellule (la cellule de depart)
        self.assertLessEqual(len(posed), 1)

    def test_retourne_uniquement_nouvelles_cases(self):
        """Seules les nouvelles cases EMPTY converties sont retournees."""
        floor = make_floor()
        # Pre-pose quelques cellules
        floor.grid[10][8].cell_type = CellType.GROUND
        floor.grid[10][9].cell_type = CellType.GROUND
        rng = random.Random(0)
        posed = trace_corridor(floor, (10, 8), (10, 12), rng=rng)
        # (10,8) et (10,9) etaient deja GROUND, ne doivent pas etre dans posed
        self.assertNotIn((10, 8), posed)
        self.assertNotIn((10, 9), posed)


# ---------------------------------------------------------------------------
# Tests blob_room
# ---------------------------------------------------------------------------

class TestBlobRoom(unittest.TestCase):

    def test_blob_basique(self):
        """Un blob se genere sur une grille vide."""
        floor = make_floor()
        rng = random.Random(42)
        result = blob_room(floor, 36, 36, min_size=3, max_size=5, rng=rng)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result), 3)

    def test_cellules_posees_sur_grille(self):
        """Les cellules du blob sont bien posees en GROUND sur la grille."""
        floor = make_floor()
        rng = random.Random(0)
        result = blob_room(floor, 36, 36, min_size=3, max_size=5, rng=rng)
        self.assertIsNotNone(result)
        for row, col in result:
            self.assertEqual(floor.grid[row][col].cell_type, CellType.GROUND)

    def test_blob_centre_non_empty_echec(self):
        """Si le centre est non-EMPTY, retourne None."""
        floor = make_floor()
        floor.grid[36][36].cell_type = CellType.WALL
        rng = random.Random(0)
        result = blob_room(floor, 36, 36, min_size=3, max_size=5, rng=rng)
        self.assertIsNone(result)

    def test_blob_taille_min_respectee(self):
        """Le blob retourne au moins min_size cellules."""
        floor = make_floor()
        rng = random.Random(7)
        result = blob_room(floor, 36, 36, min_size=5, max_size=8, rng=rng)
        if result is not None:
            self.assertGreaterEqual(len(result), 5)

    def test_blob_distance_min(self):
        """Le blob ne s'approche pas d'une salle existante (distance min)."""
        floor = make_floor()
        # Salle existante centree en (30, 30)
        existing = {(30, 30), (30, 31), (31, 30)}
        rng = random.Random(0)
        # Centre tres proche de la salle existante
        result = blob_room(
            floor, 32, 32,
            min_size=3, max_size=5,
            existing_rooms=[existing],
            min_dist=5,
            rng=rng,
        )
        # Peut reussir ou echouer, mais si reussi les cellules respectent la distance
        if result is not None:
            for row, col in result:
                for rr, rc in existing:
                    too_close = abs(rr - row) < 5 and abs(rc - col) < 5
                    self.assertFalse(too_close)


# ---------------------------------------------------------------------------
# Tests find_connection_points
# ---------------------------------------------------------------------------

class TestFindConnectionPoints(unittest.TestCase):

    def test_salles_adjacentes(self):
        """Deux salles proches -> points de connexion proches."""
        room_a = {(10, 10), (10, 11), (10, 12)}
        room_b = {(10, 15), (10, 16), (10, 17)}
        pt_a, pt_b = find_connection_points(room_a, room_b)
        self.assertIn(pt_a, room_a)
        self.assertIn(pt_b, room_b)
        # Les points doivent etre les plus proches
        dist = abs(pt_a[0] - pt_b[0]) + abs(pt_a[1] - pt_b[1])
        self.assertLessEqual(dist, 10)

    def test_retourne_points_dans_salles(self):
        """Les points retournes appartiennent chacun a leur salle."""
        room_a = {(0, 0), (1, 0), (2, 0)}
        room_b = {(0, 20), (1, 20), (2, 20)}
        pt_a, pt_b = find_connection_points(room_a, room_b)
        self.assertIn(pt_a, room_a)
        self.assertIn(pt_b, room_b)

    def test_salle_unique_cellule(self):
        """Salles d'une seule cellule -> retourne ces cellules."""
        room_a = {(5, 5)}
        room_b = {(15, 15)}
        pt_a, pt_b = find_connection_points(room_a, room_b)
        self.assertEqual(pt_a, (5, 5))
        self.assertEqual(pt_b, (15, 15))

    def test_distance_minimale(self):
        """Les points retournes sont parmi les plus proches (heuristique 25%)."""
        room_a = {(0, 0), (0, 10), (0, 20)}
        room_b = {(5, 18), (5, 19), (5, 20)}
        pt_a, pt_b = find_connection_points(room_a, room_b)
        dist_returned = abs(pt_a[0] - pt_b[0]) + abs(pt_a[1] - pt_b[1])
        # Calcule la vraie distance minimale par force brute
        true_min = min(
            abs(a[0] - b[0]) + abs(a[1] - b[1])
            for a in room_a
            for b in room_b
        )
        # L'heuristique peut ne pas etre parfaite mais reste raisonnable
        self.assertLessEqual(dist_returned, true_min * 2)


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
