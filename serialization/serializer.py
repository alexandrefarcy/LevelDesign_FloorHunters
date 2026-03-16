"""
serialization/serializer.py
Import et export JSON du projet Tower Dungeon — format Godot.

Format d'export (par étage) :
{
  "level": 1,
  "width": 72,
  "height": 72,
  "centerX": 36,
  "centerY": 36,
  "cells": {
    "x,y": { "x": int, "y": int, "type": str },
    ...
  }
}

Règles :
  - Seules les cellules non-vides sont exportées
  - Les types utilisent des tirets : stairs-down, stairs-up
  - Import invalide = SerializerError — jamais de corruption silencieuse
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.grid import CellType, GridModel, Floor, GRID_SIZE, HALF


# ---------------------------------------------------------------------------
# Mapping CellType ↔ string Godot
# ---------------------------------------------------------------------------

# CellType.value → string JSON Godot
_TO_GODOT: dict[str, str] = {
    "empty":       "empty",
    "ground":      "ground",
    "wall":        "wall",
    "enemy":       "enemy",
    "boss":        "boss",
    "treasure":    "treasure",
    "trap":        "trap",
    "camp":        "camp",
    "stairs_down": "stairs-down",
    "stairs_up":   "stairs-up",
    "spawn":       "spawn",
}

# string JSON Godot → CellType.value
_FROM_GODOT: dict[str, str] = {v: k for k, v in _TO_GODOT.items()}

VALID_GODOT_TYPES = set(_FROM_GODOT.keys())


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
        """Convertit un Floor en dict format Godot."""
        cells: dict[str, dict] = {}

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                cell = floor.grid[row][col]
                if cell.cell_type == CellType.EMPTY:
                    continue
                x, y = GridModel.index_to_coords(row, col)
                godot_type = _TO_GODOT[cell.cell_type.value]
                key = f"{x},{y}"
                cells[key] = {"x": x, "y": y, "type": godot_type}

        return {
            "level":   floor.floor_id,
            "width":   GRID_SIZE,
            "height":  GRID_SIZE,
            "centerX": HALF,
            "centerY": HALF,
            "cells":   cells,
        }

    def _godot_to_floor(self, data: dict, source_name: str) -> Floor:
        """Convertit un dict Godot en Floor."""
        from core.grid import Cell, Floor as FloorClass

        level_id = int(data.get("level", 1))
        name = f"Étage {level_id}"

        floor = FloorClass(floor_id=level_id, name=name)

        for key, cell_data in data["cells"].items():
            try:
                x = int(cell_data["x"])
                y = int(cell_data["y"])
            except (KeyError, ValueError) as exc:
                raise SerializerError(
                    f"Cellule '{key}' : coordonnées invalides dans {source_name}."
                ) from exc

            godot_type = cell_data.get("type", "")
            if godot_type not in _FROM_GODOT:
                raise SerializerError(
                    f"Cellule '{key}' : type inconnu '{godot_type}' dans {source_name}."
                )

            internal_type = _FROM_GODOT[godot_type]
            cell_type = CellType(internal_type)

            if not GridModel.is_valid_coords(x, y):
                raise SerializerError(
                    f"Cellule '{key}' : coordonnées ({x}, {y}) hors grille dans {source_name}."
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
        if not isinstance(data["cells"], dict):
            raise SerializerError(
                f"'cells' doit être un objet dans {source_name}."
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