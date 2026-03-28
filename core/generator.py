"""
core/generator.py
Orchestrateur de generation procedurale pour Tower Dungeon.

Pipeline complet :
  1. Flood fill -> detection des salles contigues (GROUND)
  2. Filtre taille min 2x1 (2 cellules minimum)
  3. MST Kruskal (networkx) sur centres geometriques
  4. +30% connexions aleatoires supplementaires
  5. Trace des couloirs (droit si aligne, sinon L avec coude aleatoire)
  6. Salle de transition organique (blob 3x3 a 8x8) si couloir > 7 cases
  7. Murs exterieurs autour de toutes les cellules non-EMPTY
  8. STAIRS_DOWN force a (0, 0)

Regle STAIRS_UP : isolee, une seule connexion vers la salle la plus proche.

Usage :
    from core.generator import Generator
    gen = Generator(seed=42)
    report = gen.run(floor)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from core.grid import CellType, Floor, GridModel, GRID_SIZE, HALF
from core.algorithms import (
    CORRIDOR_TRANSITION_LEN,
    TRANSITION_ATTEMPTS,
    TRANSITION_MIN,
    TRANSITION_MAX,
    TRANSITION_MIN_DIST,
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
# Rapport de generation
# ---------------------------------------------------------------------------

@dataclass
class GenerationReport:
    """Resume des operations effectuees par le generateur."""

    rooms_found:       int = 0
    rooms_kept:        int = 0
    rooms_discarded:   int = 0
    corridors_traced:  int = 0
    transitions_added: int = 0
    walls_placed:      int = 0
    stairs_down_set:   bool = False
    warnings:          list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Salles detectees  : {self.rooms_found}",
            f"Salles conservees : {self.rooms_kept}",
            f"Salles ignorees   : {self.rooms_discarded}",
            f"Couloirs traces   : {self.corridors_traced}",
            f"Transitions       : {self.transitions_added}",
            f"Murs poses        : {self.walls_placed}",
            f"STAIRS_DOWN (0,0) : {'OK' if self.stairs_down_set else 'ECHEC'}",
        ]
        if self.warnings:
            lines.append("Avertissements :")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class Generator:
    """Generateur procedural pour un etage de Tower Dungeon.

    Le generateur opere directement sur le Floor passe en parametre.
    Il ne supprime pas les cellules GROUND existantes (salles manuelles).

    Args:
        seed: Graine aleatoire optionnelle pour reproductibilite.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Point d'entree principal
    # ------------------------------------------------------------------

    def run(self, floor: Floor) -> GenerationReport:
        """Execute le pipeline complet de generation procedurale.

        Args:
            floor: L'etage a traiter (modifie en place).

        Returns:
            GenerationReport avec le detail des operations.
        """
        report = GenerationReport()

        # 1 - Flood fill : detection des salles
        all_rooms = flood_fill(floor)
        report.rooms_found = len(all_rooms)

        # 2 - Filtre taille minimale (2x1 = 2 cellules)
        rooms = filter_rooms(all_rooms, min_cells=2)
        report.rooms_kept = len(rooms)
        report.rooms_discarded = report.rooms_found - report.rooms_kept

        if len(rooms) == 0:
            report.warnings.append(
                "Aucune salle valide trouvee - rien a generer."
            )
            return report

        # Separe STAIRS_UP des autres salles pour traitement special
        stairs_up_room = self._find_stairs_up_room(floor, rooms)
        normal_rooms = [r for r in rooms if r is not stairs_up_room]

        # 3 - MST Kruskal sur les salles normales
        mst_edges = build_mst(normal_rooms)

        # 4 - +30% connexions supplementaires
        all_edges = add_extra_edges(mst_edges, normal_rooms, ratio=0.30)

        # 5 & 6 - Trace des couloirs + salles de transition
        transition_rooms: list[set[tuple[int, int]]] = []

        for idx_a, idx_b in all_edges:
            room_a = normal_rooms[idx_a]
            room_b = normal_rooms[idx_b]

            pt_a, pt_b = find_connection_points(room_a, room_b)
            length = corridor_length(pt_a, pt_b)

            # Salle de transition si couloir trop long
            if length > CORRIDOR_TRANSITION_LEN:
                mid_r = (pt_a[0] + pt_b[0]) // 2
                mid_c = (pt_a[1] + pt_b[1]) // 2

                blob = self._try_blob(
                    floor,
                    mid_r,
                    mid_c,
                    rooms + transition_rooms,
                )
                if blob is not None:
                    transition_rooms.append(blob)
                    report.transitions_added += 1
                    # Trace couloir A -> centre du blob -> B
                    blob_cells = list(blob)
                    blob_center_r = sum(r for r, _ in blob_cells) // len(blob_cells)
                    blob_center_c = sum(c for _, c in blob_cells) // len(blob_cells)
                    blob_pt = (blob_center_r, blob_center_c)
                    trace_corridor(floor, pt_a, blob_pt, rng=self._rng)
                    trace_corridor(floor, blob_pt, pt_b, rng=self._rng)
                else:
                    # Pas de place pour une transition -> couloir direct
                    report.warnings.append(
                        f"Transition impossible entre salles {idx_a} et {idx_b} - "
                        f"couloir direct trace."
                    )
                    trace_corridor(floor, pt_a, pt_b, rng=self._rng)
            else:
                trace_corridor(floor, pt_a, pt_b, rng=self._rng)

            report.corridors_traced += 1

        # Connexion STAIRS_UP : une seule connexion vers la salle la plus proche
        if stairs_up_room is not None:
            self._connect_stairs_up(
                floor, stairs_up_room, normal_rooms, report
            )

        # 7 - Murs exterieurs autour de toutes les cellules non-EMPTY
        walls = self._place_walls(floor)
        report.walls_placed = walls

        # 8 - STAIRS_DOWN force a (0, 0)
        report.stairs_down_set = self._place_stairs_down(floor, report)

        return report

    # ------------------------------------------------------------------
    # STAIRS_UP
    # ------------------------------------------------------------------

    def _find_stairs_up_room(
        self,
        floor: Floor,
        rooms: list[set[tuple[int, int]]],
    ) -> Optional[set[tuple[int, int]]]:
        """Retourne la salle contenant une cellule STAIRS_UP, ou None."""
        stairs_cells = set(floor.find_cells(CellType.STAIRS_UP))
        if not stairs_cells:
            return None
        for room in rooms:
            if room & stairs_cells:
                return room
        return None

    def _connect_stairs_up(
        self,
        floor: Floor,
        stairs_room: set[tuple[int, int]],
        normal_rooms: list[set[tuple[int, int]]],
        report: GenerationReport,
    ) -> None:
        """Connecte STAIRS_UP a la salle normale la plus proche (1 seul couloir)."""
        if not normal_rooms:
            report.warnings.append(
                "STAIRS_UP : aucune salle normale pour se connecter."
            )
            return

        sc_r, sc_c = room_center(stairs_room)
        best_room = min(
            normal_rooms,
            key=lambda r: (room_center(r)[0] - sc_r) ** 2
                        + (room_center(r)[1] - sc_c) ** 2,
        )

        pt_a, pt_b = find_connection_points(stairs_room, best_room)
        trace_corridor(floor, pt_a, pt_b, rng=self._rng)
        report.corridors_traced += 1

    # ------------------------------------------------------------------
    # Salle de transition (blob)
    # ------------------------------------------------------------------

    def _try_blob(
        self,
        floor: Floor,
        center_row: int,
        center_col: int,
        existing_rooms: list[set[tuple[int, int]]],
    ) -> Optional[set[tuple[int, int]]]:
        """Tente de placer un blob au centre donne (25 essais max).

        Decale legerement le centre a chaque echec.
        """
        offsets = [(0, 0)]
        for dist in range(1, 4):
            for dr in range(-dist, dist + 1):
                for dc in range(-dist, dist + 1):
                    if abs(dr) == dist or abs(dc) == dist:
                        offsets.append((dr, dc))

        attempts = min(TRANSITION_ATTEMPTS, len(offsets))
        sampled = self._rng.sample(offsets, attempts)

        for dr, dc in sampled:
            cr = center_row + dr
            cc = center_col + dc
            if not (0 <= cr < GRID_SIZE and 0 <= cc < GRID_SIZE):
                continue
            result = blob_room(
                floor,
                cr,
                cc,
                min_size=TRANSITION_MIN,
                max_size=TRANSITION_MAX,
                existing_rooms=existing_rooms,
                min_dist=TRANSITION_MIN_DIST,
                rng=self._rng,
            )
            if result is not None:
                return result

        return None

    # ------------------------------------------------------------------
    # Murs exterieurs
    # ------------------------------------------------------------------

    def _place_walls(self, floor: Floor) -> int:
        """Place des murs (WALL) sur toutes les cases EMPTY adjacentes a une case non-EMPTY.

        Seules les cases EMPTY sont converties en WALL.
        Les 4 directions cardinales sont verifiees.

        Returns:
            Nombre de murs places.
        """
        to_wall: set[tuple[int, int]] = set()

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                if floor.grid[row][col].cell_type == CellType.EMPTY:
                    continue
                # Case non-EMPTY : ses voisins EMPTY deviennent des murs
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = row + dr, col + dc
                    if not (0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE):
                        continue
                    if floor.grid[nr][nc].cell_type == CellType.EMPTY:
                        to_wall.add((nr, nc))

        for row, col in to_wall:
            floor.grid[row][col].cell_type = CellType.WALL

        return len(to_wall)

    # ------------------------------------------------------------------
    # STAIRS_DOWN a (0, 0)
    # ------------------------------------------------------------------

    def _place_stairs_down(
        self, floor: Floor, report: GenerationReport
    ) -> bool:
        """Force STAIRS_DOWN a la case (0, 0) en coordonnees centrees.

        Si la case (0,0) est EMPTY apres generation, leve un avertissement.
        STAIRS_DOWN ecrase toute cellule existante a cette position.

        Returns:
            True si la pose a reussi.
        """
        try:
            row, col = GridModel.coords_to_index(0, 0)
        except ValueError:
            report.warnings.append(
                "Impossible de convertir (0,0) en index grille."
            )
            return False

        current = floor.grid[row][col].cell_type
        if current == CellType.EMPTY:
            report.warnings.append(
                "La case (0,0) est EMPTY apres generation : "
                "STAIRS_DOWN pose sur une case isolee. "
                "Verifie que une salle manuelle couvre (0,0) ou ses alentours."
            )

        floor.grid[row][col].cell_type = CellType.STAIRS_DOWN
        return True
