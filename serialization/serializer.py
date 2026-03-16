"""
io/serializer.py
Import et export JSON du projet Tower Dungeon.

Règles permanentes :
  - Import invalide = exception SerializerError — jamais de corruption silencieuse
  - Le schéma JSON est versionné (champ "version")
  - Les chemins custom_image sont toujours relatifs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

from core.grid import GridModel, GRID_SIZE


# ---------------------------------------------------------------------------
# Schéma JSON (version 1)
# ---------------------------------------------------------------------------

_CELL_SCHEMA = {
    "type": "object",
    "required": ["type", "custom_image"],
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "empty", "ground", "wall", "enemy", "boss",
                "treasure", "trap", "camp",
                "stairs_down", "stairs_up", "spawn",
            ],
        },
        "custom_image": {
            "type": ["string", "null"],
        },
    },
}

_FLOOR_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "grid"],
    "additionalProperties": False,
    "properties": {
        "id":   {"type": "integer", "minimum": 1},
        "name": {"type": "string",  "minLength": 1},
        "grid": {
            "type": "array",
            "minItems": GRID_SIZE,
            "maxItems": GRID_SIZE,
            "items": {
                "type": "array",
                "minItems": GRID_SIZE,
                "maxItems": GRID_SIZE,
                "items": _CELL_SCHEMA,
            },
        },
    },
}

JSON_SCHEMA_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TowerDungeonProject",
    "type": "object",
    "required": ["version", "floors"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "integer", "enum": [1]},
        "floors": {
            "type": "array",
            "minItems": 1,
            "items": _FLOOR_SCHEMA,
        },
    },
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
    """Gère l'export et l'import JSON d'un GridModel.

    Usage :
        s = Serializer()
        s.save(model, Path("mon_projet.json"))
        model = s.load(Path("mon_projet.json"))
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """
        Args:
            base_dir : Répertoire de référence pour résoudre les chemins
                       relatifs des sprites custom. Si None, le répertoire
                       courant est utilisé.
        """
        self.base_dir: Path = base_dir or Path.cwd()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def save(self, model: GridModel, path: Path) -> None:
        """Sérialise le GridModel et l'écrit dans un fichier JSON.

        Args:
            model : Le modèle à exporter.
            path  : Chemin complet du fichier de sortie.

        Raises:
            SerializerError: En cas d'erreur d'écriture.
        """
        if model.floor_count == 0:
            raise SerializerError(
                "Impossible d'exporter : le projet ne contient aucun étage."
            )

        data = model.to_dict()

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise SerializerError(f"Erreur d'écriture : {exc}") from exc

    def to_json_string(self, model: GridModel, indent: int = 2) -> str:
        """Retourne la représentation JSON du modèle sous forme de chaîne.

        Utile pour les tests ou la prévisualisation.
        """
        if model.floor_count == 0:
            raise SerializerError("Le projet ne contient aucun étage.")
        return json.dumps(model.to_dict(), ensure_ascii=False, indent=indent)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def load(self, path: Path) -> GridModel:
        """Charge un fichier JSON et retourne le GridModel correspondant.

        Args:
            path : Chemin du fichier JSON à charger.

        Raises:
            SerializerError: Si le fichier est introuvable, invalide
                             ou ne correspond pas au schéma attendu.
        """
        if not path.exists():
            raise SerializerError(f"Fichier introuvable : {path}")

        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            raise SerializerError(f"Erreur de lecture : {exc}") from exc

        return self.from_json_string(raw, source_name=str(path))

    def from_json_string(self, raw: str, source_name: str = "<chaîne>") -> GridModel:
        """Parse une chaîne JSON et retourne le GridModel.

        Args:
            raw         : Contenu JSON brut.
            source_name : Nom du fichier (pour les messages d'erreur).

        Raises:
            SerializerError: Si le JSON est malformé ou invalide.
        """
        # 1. Parse JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SerializerError(
                f"JSON malformé dans {source_name} : {exc}"
            ) from exc

        # 2. Validation de version avant jsonschema
        version = data.get("version")
        if version != 1:
            raise SerializerError(
                f"Version JSON non supportée : {version!r}. "
                "Seule la version 1 est acceptée."
            )

        # 3. Validation du schéma complet
        self._validate_schema(data, source_name)

        # 4. Reconstruction du modèle
        try:
            model = GridModel.from_dict(data)
        except (KeyError, ValueError, TypeError) as exc:
            raise SerializerError(
                f"Erreur lors de la reconstruction du modèle : {exc}"
            ) from exc

        return model

    # ------------------------------------------------------------------
    # Validation interne
    # ------------------------------------------------------------------

    def _validate_schema(self, data: dict, source_name: str) -> None:
        """Valide data contre JSON_SCHEMA_V1.

        Si jsonschema n'est pas installé, effectue une validation minimale
        manuelle (vérification des clés obligatoires et dimensions de grille).
        """
        if _HAS_JSONSCHEMA:
            try:
                jsonschema.validate(instance=data, schema=JSON_SCHEMA_V1)
            except jsonschema.ValidationError as exc:
                raise SerializerError(
                    f"Schéma JSON invalide dans {source_name} :\n"
                    f"  Chemin : {' → '.join(str(p) for p in exc.absolute_path)}\n"
                    f"  Erreur : {exc.message}"
                ) from exc
        else:
            # Validation manuelle minimale
            self._validate_minimal(data, source_name)

    def _validate_minimal(self, data: dict, source_name: str) -> None:
        """Validation sans jsonschema — vérifie les contraintes essentielles."""
        if "floors" not in data:
            raise SerializerError(
                f"Champ 'floors' manquant dans {source_name}."
            )
        if not isinstance(data["floors"], list) or len(data["floors"]) == 0:
            raise SerializerError(
                f"'floors' doit être une liste non vide dans {source_name}."
            )

        valid_types = {
            "empty", "ground", "wall", "enemy", "boss",
            "treasure", "trap", "camp",
            "stairs_down", "stairs_up", "spawn",
        }

        for fi, floor in enumerate(data["floors"]):
            for key in ("id", "name", "grid"):
                if key not in floor:
                    raise SerializerError(
                        f"Étage {fi} : champ '{key}' manquant dans {source_name}."
                    )

            grid = floor["grid"]
            if len(grid) != GRID_SIZE:
                raise SerializerError(
                    f"Étage {fi} : la grille doit avoir {GRID_SIZE} lignes, "
                    f"trouvé {len(grid)} dans {source_name}."
                )
            for ri, row in enumerate(grid):
                if len(row) != GRID_SIZE:
                    raise SerializerError(
                        f"Étage {fi}, ligne {ri} : "
                        f"{GRID_SIZE} colonnes attendues, "
                        f"trouvé {len(row)} dans {source_name}."
                    )
                for ci, cell in enumerate(row):
                    if "type" not in cell:
                        raise SerializerError(
                            f"Étage {fi} [{ri}][{ci}] : champ 'type' manquant."
                        )
                    if cell["type"] not in valid_types:
                        raise SerializerError(
                            f"Étage {fi} [{ri}][{ci}] : "
                            f"type inconnu {cell['type']!r}."
                        )

    # ------------------------------------------------------------------
    # Utilitaires chemins
    # ------------------------------------------------------------------

    def make_relative(self, absolute_path: str) -> str:
        """Convertit un chemin absolu en chemin relatif par rapport à base_dir."""
        try:
            return str(Path(absolute_path).relative_to(self.base_dir))
        except ValueError:
            return absolute_path

    def resolve(self, relative_path: str) -> Path:
        """Résout un chemin relatif en chemin absolu depuis base_dir."""
        return self.base_dir / relative_path