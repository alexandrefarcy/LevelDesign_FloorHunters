"""
core/populator.py
Peuplement automatique d'entites pour Tower Dungeon.

Pipeline :
  1. Efface toutes les entites existantes (ENEMY, TREASURE, TRAP)
  2. Detecte les salles (flood fill GROUND) et les couloirs
  3. Place les entites selon les densites et regles de placement :
     - ENEMY    : cellules GROUND de salles, jamais couloirs ni (0,0)
     - TREASURE : coins de salles (2+ voisins EMPTY), jamais couloirs
     - TRAP     : couloirs etroits (2 voisins GROUND opposes)

Usage :
    from core.populator import Populator
    pop = Populator(seed=42)
    report = pop.run(floor,
                     enemy_density=0.20,
                     treasure_density=0.05,
                     trap_density=0.15)
    print(report.summary())
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from core.grid import CellType, Floor, GridModel, GRID_SIZE


# ---------------------------------------------------------------------------
# Entites gerees par le peuplement
# ---------------------------------------------------------------------------

MANAGED_TYPES = {CellType.ENEMY, CellType.TREASURE, CellType.TRAP}


# ---------------------------------------------------------------------------
# Rapport de peuplemen
# ---------------------------------------------------------------------------

@dataclass
class PopulationReport:
    """Resume des operations effectuees par le peupleur."""

    enemies_placed:   int = 0
    treasures_placed: int = 0
    traps_placed:     int = 0
    cells_cleared:    int = 0
    warnings:         list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Cellules effacees  : {self.cells_cleared}",
            f"Ennemis places     : {self.enemies_placed}",
            f"Tresors places     : {self.treasures_placed}",
            f"Pieges places      : {self.traps_placed}",
            f"Total entites      : {self.total}",
        ]
        if self.warnings:
            lines.append("Avertissements :")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)

    @property
    def total(self) -> int:
        return self.enemies_placed + self.treasures_placed + self.traps_placed


# ---------------------------------------------------------------------------
# Populator
# ---------------------------------------------------------------------------

class Populator:
    """Peupleur d'entites pour un etage de Tower Dungeon.

    Opere directement sur le Floor passe en parametre.
    Efface les entites gerees avant de replacer.

    Args:
        seed: Graine aleatoire optionnelle pour reproductibilite.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Point d'entree principal
    # ------------------------------------------------------------------

    def run(
        self,
        floor: Floor,
        enemy_density:    float = 0.20,
        treasure_density: float = 0.05,
        trap_density:     float = 0.15,
    ) -> PopulationReport:
        """Execute le pipeline complet de peuplement.

        Args:
            floor:            L'etage a peupler (modifie en place).
            enemy_density:    Proportion de cellules GROUND eligibles
                              converties en ENEMY (0.0 a 1.0).
            treasure_density: Proportion de coins eligibles en TREASURE.
            trap_density:     Proportion de couloirs eligibles en TRAP.

        Returns:
            PopulationReport avec le detail des operations.
        """
        report = PopulationReport()

        # Clamp des densites
        enemy_density    = max(0.0, min(1.0, enemy_density))
        treasure_density = max(0.0, min(1.0, treasure_density))
        trap_density     = max(0.0, min(1.0, trap_density))

        # 1 - Efface les entites existantes
        report.cells_cleared = self._clear_entities(floor)

        # 2 - Calcule l'index (0,0) pour l'exclure
        origin_row, origin_col = GridModel.coords_to_index(0, 0)

        # 3 - Detecte les candidats
        room_cells    = self._find_room_cells(floor, origin_row, origin_col)
        corridor_cells = self._find_corridor_cells(floor, origin_row, origin_col)
        corner_cells  = self._find_corner_cells(floor, room_cells)
        narrow_corridors = self._find_narrow_corridors(floor, corridor_cells)

        # 4 - Place les entites
        report.enemies_placed = self._place_entities(
            floor, room_cells, enemy_density, CellType.ENEMY, report
        )
        report.treasures_placed = self._place_entities(
            floor, corner_cells, treasure_density, CellType.TREASURE, report
        )
        report.traps_placed = self._place_entities(
            floor, narrow_corridors, trap_density, CellType.TRAP, report
        )

        if report.total == 0 and not report.warnings:
            report.warnings.append(
                "Aucune entite placee -- verifie que l'etage a ete genere."
            )

        return report

    # ------------------------------------------------------------------
    # Effacement
    # ------------------------------------------------------------------

    def _clear_entities(self, floor: Floor) -> int:
        """Efface toutes les cellules ENEMY, TREASURE, TRAP -> GROUND."""
        count = 0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if floor.grid[r][c].cell_type in MANAGED_TYPES:
                    floor.grid[r][c].cell_type = CellType.GROUND
                    count += 1
        return count

    # ------------------------------------------------------------------
    # Detection des candidats
    # ------------------------------------------------------------------

    def _is_ground(self, floor: Floor, r: int, c: int) -> bool:
        if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
            return False
        return floor.grid[r][c].cell_type == CellType.GROUND

    def _ground_neighbor_count(self, floor: Floor, r: int, c: int) -> int:
        """Nombre de voisins cardinaux GROUND."""
        return sum(
            1 for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if self._is_ground(floor, r + dr, c + dc)
        )

    def _empty_neighbor_count(self, floor: Floor, r: int, c: int) -> int:
        """Nombre de voisins cardinaux EMPTY."""
        count = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE):
                count += 1  # bord de grille compte comme EMPTY
            elif floor.grid[nr][nc].cell_type == CellType.EMPTY:
                count += 1
        return count

    def _find_room_cells(
        self,
        floor: Floor,
        origin_row: int,
        origin_col: int,
    ) -> list[tuple[int, int]]:
        """Retourne les cellules GROUND de salles (3+ voisins GROUND).

        Exclut (0,0) et les couloirs (cellules avec peu de voisins GROUND).
        """
        cells = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if floor.grid[r][c].cell_type != CellType.GROUND:
                    continue
                if r == origin_row and c == origin_col:
                    continue
                # Salle = cellule avec au moins 2 voisins GROUND (pas un couloir isole)
                if self._ground_neighbor_count(floor, r, c) >= 2:
                    cells.append((r, c))
        return cells

    def _find_corridor_cells(
        self,
        floor: Floor,
        origin_row: int,
        origin_col: int,
    ) -> list[tuple[int, int]]:
        """Retourne les cellules GROUND de couloirs (1 ou 2 voisins GROUND)."""
        cells = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if floor.grid[r][c].cell_type != CellType.GROUND:
                    continue
                if r == origin_row and c == origin_col:
                    continue
                n = self._ground_neighbor_count(floor, r, c)
                if n <= 2:
                    cells.append((r, c))
        return cells

    def _find_corner_cells(
        self,
        floor: Floor,
        room_cells: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Filtre les cellules de salle en coins (2+ voisins EMPTY).

        Un coin est une cellule de salle avec peu de voisins pleins --
        ideale pour un tresor cache.
        """
        return [
            (r, c) for r, c in room_cells
            if self._empty_neighbor_count(floor, r, c) >= 2
        ]

    def _find_narrow_corridors(
        self,
        floor: Floor,
        corridor_cells: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Filtre les couloirs etroits : exactement 2 voisins GROUND opposes.

        N/S opposes (couloir vertical) ou E/O opposes (couloir horizontal).
        Ces cases sont les meilleures pour des pieges.
        """
        narrow = []
        for r, c in corridor_cells:
            n_ground = self._is_ground(floor, r - 1, c)
            s_ground = self._is_ground(floor, r + 1, c)
            e_ground = self._is_ground(floor, r, c + 1)
            o_ground = self._is_ground(floor, r, c - 1)

            vertical   = n_ground and s_ground and not e_ground and not o_ground
            horizontal = e_ground and o_ground and not n_ground and not s_ground

            if vertical or horizontal:
                narrow.append((r, c))
        return narrow

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def _place_entities(
        self,
        floor: Floor,
        candidates: list[tuple[int, int]],
        density: float,
        cell_type: CellType,
        report: PopulationReport,
    ) -> int:
        """Place des entites sur un sous-ensemble aleatoire des candidats.

        Args:
            candidates: Liste de (row, col) eligibles.
            density:    Proportion a peupler (0.0 a 1.0).
            cell_type:  Type a placer.

        Returns:
            Nombre d'entites placees.
        """
        if not candidates or density <= 0.0:
            return 0

        # Filtre les cases encore GROUND (pas ecrasees par un placement precedent)
        available = [
            (r, c) for r, c in candidates
            if floor.grid[r][c].cell_type == CellType.GROUND
        ]

        if not available:
            report.warnings.append(
                f"Aucune case disponible pour {cell_type.value}."
            )
            return 0

        count = max(1, round(len(available) * density))
        count = min(count, len(available))

        chosen = self._rng.sample(available, count)
        for r, c in chosen:
            floor.grid[r][c].cell_type = cell_type

        return len(chosen)
