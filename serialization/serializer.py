"""
serialization/serializer.py
Import et export JSON du projet Tower Dungeon  format Godot.

Format d'export (par étage) :
{
  "level": 1,
  "width": 72,
  "height": 72,
  "centerX": 36,
  "centerY": 36,
  "cells": [
    { "pos": [x, y] },
    { "pos": [x, y], "type": "camp" },
    { "pos": [x, y], "type": "wall", "mask": 5, "rot_y": 0.0 }
  ]
}

Règles :
  - Seules les cellules non-EMPTY sont exportées (liste sparse)
  - pos = [x, y] en coordonnées centrées Godot
  - "type" omis si GROUND (valeur par défaut implicite)
  - Les types utilisent des underscores : stairs_down, stairs_up
  - "mask" et "rot_y" présents uniquement sur les cellules WALL
    mask : bitmask 4 bits N=1/E=2/S=4/O=8  voisin plein = non-EMPTY
    rot_y : rotation en degrés autour de l'axe Y (convention Godot,
            sens anti-horaire vu du dessus, 0° = face vers -Z)
  - Import invalide = SerializerError  jamais de corruption silencieuse
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.grid import CellType, GridModel, Floor, GRID_SIZE, HALF


# ---------------------------------------------------------------------------
# Mapping CellType ↔ string Godot
# ---------------------------------------------------------------------------

# CellType.value → string JSON Godot (underscores)
_TO_GODOT: dict[str, str] = {
    "empty":       "empty",
    "ground":      "ground",
    "wall":        "wall",
    "enemy":       "enemy",
    "boss":        "boss",
    "treasure":    "treasure",
    "trap":        "trap",
    "camp":        "camp",
    "stairs_down": "stairs_down",
    "stairs_up":   "stairs_up",
    "spawn":       "spawn",
}

# string JSON Godot → CellType.value
_FROM_GODOT: dict[str, str] = {v: k for k, v in _TO_GODOT.items()}

VALID_GODOT_TYPES = set(_FROM_GODOT.keys())


# ---------------------------------------------------------------------------
# Table bitmask → rot_y pour les murs
#
# Encodage des voisins (axe Y vers le haut, sens anti-horaire vu du dessus) :
#   N = bit 0 (1)   voisin en y+1
#   E = bit 1 (2)   voisin en x+1
#   S = bit 2 (4)   voisin en y-1
#   O = bit 3 (8)   voisin en x-1
#
# rot_y : degrés, axe Y Godot, 0° = face vers -Z
# ---------------------------------------------------------------------------

_WALL_ROT_Y: dict[int, float] = {
    0:  0.0,    # isolé
    1:  0.0,    # N
    2:  90.0,   # E
    3:  90.0,   # N+E  coin
    4:  180.0,  # S
    5:  0.0,    # N+S  couloir
    6:  180.0,  # E+S  coin
    7:  90.0,   # N+E+S  T sans O
    8:  270.0,  # O
    9:  0.0,    # N+O  coin
    10: 90.0,   # E+O  couloir
    11: 0.0,    # N+E+O  T sans S
    12: 270.0,  # S+O  coin
    13: 270.0,  # N+S+O  T sans E
    14: 180.0,  # E+S+O  T sans N
    15: 0.0,    # N+E+S+O  croix
}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class SerializerError(Exception):
    """Levée pour tout problème d'import/export."""


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

class Serializer:
    """Export et import JSON format Godot d'un GridModel.

    Un fichier = un étage. L'export d'un projet multi-étages
    produit un fichier par étage (level_1.json, level_2.json…)
    ou un fichier unique si un seul étage.

    Usage :
        s = Serializer()
        s.save(model, Path("level_1.json"))   # étage actif
        model = s.load(Path("level_1.json"))
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir: Path = base_dir or Path.cwd()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def save(self, model: GridModel, path: Path) -> None:
        """Exporte l'étage actif en JSON format Godot.

        Si le projet a plusieurs étages, exporte uniquement l'étage actif.
        Pour exporter tous les étages, utiliser save_all().
        """
        if model.floor_count == 0:
            raise SerializerError("Le projet ne contient aucun étage.")

        floor = model.get_active_floor()
        if floor is None:
            raise SerializerError("Aucun étage actif.")

        data = self._floor_to_godot(floor)
        self._write_json(data, path)

    def save_all(self, model: GridModel, directory: Path) -> list[Path]:
        """Exporte tous les étages, un fichier par étage.

        Retourne la liste des fichiers créés.
        """
        if model.floor_count == 0:
            raise SerializerError("Le projet ne contient aucun étage.")

        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for floor in model.floors:
            filename = f"level_{floor.floor_id}.json"
            out = directory / filename
            data = self._floor_to_godot(floor)
            self._write_json(data, out)
            paths.append(out)
        return paths

    def to_json_string(self, model: GridModel, indent: int = 2) -> str:
        """Retourne le JSON de l'étage actif sous forme de chaîne."""
        if model.floor_count == 0:
            raise SerializerError("Le projet ne contient aucun étage.")
        floor = model.get_active_floor()
        if floor is None:
            raise SerializerError("Aucun étage actif.")
        return json.dumps(self._floor_to_godot(floor),
                          ensure_ascii=False, indent=indent)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def load(self, path: Path) -> GridModel:
        """Charge un fichier JSON Godot et retourne un GridModel à un étage."""
        if not path.exists():
            raise SerializerError(f"Fichier introuvable : {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            raise SerializerError(f"Erreur de lecture : {exc}") from exc
        return self.from_json_string(raw, source_name=str(path))

    def from_json_string(self, raw: str,
                         source_name: str = "<chaîne>") -> GridModel:
        """Parse un JSON Godot et retourne un GridModel."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SerializerError(
                f"JSON malformé dans {source_name} : {exc}"
            ) from exc

        self._validate_godot(data, source_name)

        floor = self._godot_to_floor(data, source_name)
        model = GridModel()
        model.floors.append(floor)
        model._next_id = floor.floor_id + 1
        model._active_floor_id = floor.floor_id
        return model

    # ------------------------------------------------------------------
    # Conversion floor ↔ dict Godot
    # ------------------------------------------------------------------

    def _floor_to_godot(self, floor: Floor) -> dict:
        """Convertit un Floor en dict format Godot.

        - Liste sparse : seules les cellules non-EMPTY sont incluses
        - GROUND : {"pos": [x, y]}  type omis car valeur par défaut
        - Autres : {"pos": [x, y], "type": "..."}
        - WALL  : {"pos": [x, y], "type": "wall", "mask": int, "rot_y": float}
        """
        cells: list[dict] = []

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                cell = floor.grid[row][col]
                if cell.cell_type == CellType.EMPTY:
                    continue

                x, y = GridModel.index_to_coords(row, col)

                if cell.cell_type == CellType.GROUND:
                    # Type omis  GROUND est la valeur par défaut implicite
                    cells.append({"pos": [x, y]})

                elif cell.cell_type == CellType.WALL:
                    mask = self._compute_wall_mask(floor, row, col)
                    rot_y = _WALL_ROT_Y[mask]
                    cells.append({
                        "pos":   [x, y],
                        "type":  "wall",
                        "mask":  mask,
                        "rot_y": rot_y,
                    })

                else:
                    godot_type = _TO_GODOT[cell.cell_type.value]
                    cells.append({"pos": [x, y], "type": godot_type})

        return {
            "level":   floor.floor_id,
            "width":   GRID_SIZE,
            "height":  GRID_SIZE,
            "centerX": HALF,
            "centerY": HALF,
            "cells":   cells,
        }

    def _compute_wall_mask(self, floor: Floor, row: int, col: int) -> int:
        """Calcule le bitmask 4 bits d'un mur selon ses voisins cardinaux.

        Un voisin est "plein" s'il est non-EMPTY (sol, mur, entité…).
        Encodage : N=1 (y+1 → row-1), E=2 (x+1 → col+1),
                   S=4 (y-1 → row+1), O=8 (x-1 → col-1)
        """
        def is_solid(r: int, c: int) -> bool:
            if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
                return False
            return floor.grid[r][c].cell_type != CellType.EMPTY

        mask = 0
        if is_solid(row - 1, col):  # N  (y+1)
            mask |= 1
        if is_solid(row, col + 1):  # E  (x+1)
            mask |= 2
        if is_solid(row + 1, col):  # S  (y-1)
            mask |= 4
        if is_solid(row, col - 1):  # O  (x-1)
            mask |= 8
        return mask

    def _godot_to_floor(self, data: dict, source_name: str) -> Floor:
        """Convertit un dict Godot en Floor.

        - cells est une liste sparse
        - pos[0] = x, pos[1] = y (coordonnées centrées)
        - "type" absent → GROUND par défaut
        - "mask" et "rot_y" ignorés (données Godot only)
        """
        from core.grid import Cell, Floor as FloorClass

        level_id = int(data.get("level", 1))
        name = f"Étage {level_id}"

        floor = FloorClass(floor_id=level_id, name=name)

        for i, cell_data in enumerate(data["cells"]):
            try:
                pos = cell_data["pos"]
                x = int(pos[0])
                y = int(pos[1])
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise SerializerError(
                    f"Cellule #{i} : 'pos' invalide dans {source_name}."
                ) from exc

            godot_type = cell_data.get("type", "ground")
            if godot_type not in _FROM_GODOT:
                raise SerializerError(
                    f"Cellule #{i} : type inconnu '{godot_type}' dans {source_name}."
                )

            internal_type = _FROM_GODOT[godot_type]
            cell_type = CellType(internal_type)

            if not GridModel.is_valid_coords(x, y):
                raise SerializerError(
                    f"Cellule #{i} : coordonnées ({x}, {y}) hors grille dans {source_name}."
                )

            floor.set_cell_at(x, y, cell_type)

        return floor

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_godot(self, data: dict, source_name: str) -> None:
        """Validation minimale du format Godot."""
        if not isinstance(data, dict):
            raise SerializerError(
                f"Le JSON doit être un objet, trouvé {type(data).__name__} dans {source_name}."
            )
        if "cells" not in data:
            raise SerializerError(
                f"Champ 'cells' manquant dans {source_name}."
            )
        if not isinstance(data["cells"], list):
            raise SerializerError(
                f"'cells' doit être un tableau dans {source_name}."
            )

    # ------------------------------------------------------------------
    # Utilitaire
    # ------------------------------------------------------------------

    def _write_json(self, data: dict, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise SerializerError(f"Erreur d'écriture : {exc}") from exc

    def make_relative(self, absolute_path: str) -> str:
        try:
            return str(Path(absolute_path).relative_to(self.base_dir))
        except ValueError:
            return absolute_path

    def resolve(self, relative_path: str) -> Path:
        return self.base_dir / relative_path