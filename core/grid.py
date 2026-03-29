"""
core/grid.py
Modèle de données du Tower Dungeon Level Editor.

Contient :
  - CellType  : enum de tous les types de cellules
  - Cell      : dataclass d'une cellule (type + sprite custom)
  - Floor     : un étage complet (grille 72×72 + métadonnées)
  - GridModel : conteneur multi-étages + conversions de coordonnées
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes de la grille
# ---------------------------------------------------------------------------

GRID_SIZE = 72          # Nombre de colonnes ET de lignes
HALF = GRID_SIZE // 2   # 36  demi-taille pour le centrage des coordonnées


# ---------------------------------------------------------------------------
# CellType
# ---------------------------------------------------------------------------

class CellType(str, Enum):
    """Types de cellules disponibles dans l'éditeur.

    La valeur string correspond exactement à la clé utilisée dans le JSON
    d'export/import  ne pas modifier sans versionner le schéma.
    """
    EMPTY        = "empty"
    GROUND       = "ground"
    WALL         = "wall"
    ENEMY        = "enemy"
    BOSS         = "boss"
    TREASURE     = "treasure"
    TRAP         = "trap"
    CAMP         = "camp"
    STAIRS_DOWN  = "stairs_down"
    STAIRS_UP    = "stairs_up"
    SPAWN        = "spawn"

    # ERASER n'est pas une cellule  c'est un outil UI.
    # Il ne doit jamais être stocké dans la grille.


# Libellés affichés dans la palette d'outils
CELL_LABELS: dict[CellType, str] = {
    CellType.EMPTY:        "Vide",
    CellType.GROUND:       "Sol",
    CellType.WALL:         "Mur",
    CellType.ENEMY:        "Ennemi",
    CellType.BOSS:         "Boss",
    CellType.TREASURE:     "Trésor",
    CellType.TRAP:         "Piège",
    CellType.CAMP:         "Camp",
    CellType.STAIRS_DOWN:  "Escalier bas",
    CellType.STAIRS_UP:    "Escalier haut",
    CellType.SPAWN:        "Spawn",
}

# Emojis affichés dans la palette d'outils
CELL_EMOJIS: dict[CellType, str] = {
    CellType.EMPTY:        "·",
    CellType.GROUND:       "🟫",
    CellType.WALL:         "🧱",
    CellType.ENEMY:        "👾",
    CellType.BOSS:         "👹",
    CellType.TREASURE:     "💎",
    CellType.TRAP:         "🔥",
    CellType.CAMP:         "⛺",
    CellType.STAIRS_DOWN:  "🪜↓",
    CellType.STAIRS_UP:    "🪜↑",
    CellType.SPAWN:        "📍",
}

# Couleurs de rendu par défaut (R, G, B) utilisées quand aucun sprite custom
CELL_COLORS: dict[CellType, tuple[int, int, int]] = {
    CellType.EMPTY:        (30,  30,  35),
    CellType.GROUND:       (139, 115,  85),
    CellType.WALL:         (80,  80,  90),
    CellType.ENEMY:        (200,  60,  60),
    CellType.BOSS:         (160,  30, 160),
    CellType.TREASURE:     (220, 180,  40),
    CellType.TRAP:         (220,  90,  20),
    CellType.CAMP:         (60,  160,  80),
    CellType.STAIRS_DOWN:  (60,  120, 220),
    CellType.STAIRS_UP:    (40,  200, 200),
    CellType.SPAWN:        (240, 240,  60),
}


# ---------------------------------------------------------------------------
# CustomCellRegistry -- types de cellules définis par l'utilisateur
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dataclass

@_dataclass
class CustomCellDef:
    """Définition d'un type de cellule personnalisé.

    Attributes:
        type_id    : identifiant string unique (ex: "garde"), utilisé dans le JSON
        label      : nom affiché dans la palette (ex: "Garde")
        color      : couleur de fond (R, G, B)
        icon_unicode : icone Unicode à afficher (peut être vide)
        icon_path  : chemin absolu vers un PNG, ou None
    """
    type_id:       str
    label:         str
    color:         tuple[int, int, int] = (100, 100, 120)
    icon_unicode:  str = "?"
    icon_path:     Optional[str] = None


class CustomCellRegistry:
    """Registre global des types et remplacements d'icones custom.

    Deux catégories :
    - _custom_types    : nouveaux CellTypes créés par l'utilisateur
    - _icon_overrides  : remplacement visuel d'un CellType existant
                         (unicode ou PNG, le type JSON reste inchangé)
    """

    def __init__(self) -> None:
        self._custom_types:   dict[str, CustomCellDef] = {}
        self._icon_overrides: dict[str, CustomCellDef] = {}

    # -- Types custom -------------------------------------------------------

    def register(self, defn: CustomCellDef) -> None:
        """Enregistre un nouveau type custom. Ecrase si type_id déjà existant."""
        self._custom_types[defn.type_id] = defn

    def unregister(self, type_id: str) -> None:
        """Supprime un type custom."""
        self._custom_types.pop(type_id, None)

    def get(self, type_id: str) -> Optional[CustomCellDef]:
        """Retourne la définition d'un type custom, ou None."""
        return self._custom_types.get(type_id)

    def is_custom(self, type_id: str) -> bool:
        """Retourne True si type_id est un type custom (pas un CellType natif)."""
        return type_id in self._custom_types

    def all_custom(self) -> list[CustomCellDef]:
        """Retourne tous les types custom enregistrés."""
        return list(self._custom_types.values())

    # -- Remplacements visuels ----------------------------------------------

    def set_override(self, cell_type_value: str, defn: CustomCellDef) -> None:
        """Définit un remplacement visuel pour un CellType existant."""
        self._icon_overrides[cell_type_value] = defn

    def clear_override(self, cell_type_value: str) -> None:
        """Supprime le remplacement visuel d'un CellType existant."""
        self._icon_overrides.pop(cell_type_value, None)

    def get_override(self, cell_type_value: str) -> Optional[CustomCellDef]:
        """Retourne le remplacement visuel d'un CellType, ou None."""
        return self._icon_overrides.get(cell_type_value)

    def all_overrides(self) -> dict[str, CustomCellDef]:
        """Retourne tous les remplacements visuels."""
        return dict(self._icon_overrides)

    # -- Sérialisation ------------------------------------------------------

    def to_dict(self) -> dict:
        """Sérialise le registre en dict JSON-compatible."""
        def _def_to_dict(d: CustomCellDef) -> dict:
            return {
                "type_id":      d.type_id,
                "label":        d.label,
                "color":        list(d.color),
                "icon_unicode": d.icon_unicode,
                "icon_path":    d.icon_path,
            }
        return {
            "custom_types":   [_def_to_dict(d) for d in self._custom_types.values()],
            "icon_overrides": {k: _def_to_dict(v) for k, v in self._icon_overrides.items()},
        }

    def from_dict(self, data: dict) -> None:
        """Restaure le registre depuis un dict. Ne réinitialise pas -- fusionne."""
        def _dict_to_def(d: dict) -> CustomCellDef:
            return CustomCellDef(
                type_id=d["type_id"],
                label=d["label"],
                color=tuple(d.get("color", [100, 100, 120])),
                icon_unicode=d.get("icon_unicode", "?"),
                icon_path=d.get("icon_path"),
            )
        for item in data.get("custom_types", []):
            try:
                self.register(_dict_to_def(item))
            except (KeyError, TypeError):
                pass
        for key, item in data.get("icon_overrides", {}).items():
            try:
                self.set_override(key, _dict_to_def(item))
            except (KeyError, TypeError):
                pass

    def clear(self) -> None:
        """Vide entièrement le registre."""
        self._custom_types.clear()
        self._icon_overrides.clear()


# Instance globale partagée par tous les modules
CUSTOM_REGISTRY = CustomCellRegistry()

@dataclass
class Cell:
    """Une cellule de la grille.

    Attributes:
        cell_type    : Type de la cellule (CellType).
        custom_image : Chemin relatif vers un sprite personnalisé,
                       ou None pour utiliser le rendu par défaut.
    """
    cell_type:    CellType = CellType.EMPTY
    custom_image: Optional[str] = None

    def is_empty(self) -> bool:
        return self.cell_type == CellType.EMPTY

    def is_passable(self) -> bool:
        """Retourne True si la cellule est praticable (non-mur, non-vide)."""
        return self.cell_type not in (CellType.EMPTY, CellType.WALL)

    def clone(self) -> "Cell":
        return Cell(cell_type=self.cell_type, custom_image=self.custom_image)

    def to_dict(self) -> dict:
        return {
            "type": self.cell_type.value,
            "custom_image": self.custom_image,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Cell":
        return cls(
            cell_type=CellType(data["type"]),
            custom_image=data.get("custom_image"),
        )


# ---------------------------------------------------------------------------
# Floor
# ---------------------------------------------------------------------------

@dataclass
class Floor:
    """Un étage de la tour.

    La grille est indexée [row][col] avec row ∈ [0, 71] et col ∈ [0, 71].
    L'origine (0, 0) en coordonnées centrées correspond à l'index
    (HALF, HALF) = (36, 36).

    Attributes:
        floor_id : Identifiant unique de l'étage (entier ≥ 1).
        name     : Nom affiché dans l'interface.
        grid     : Grille 72×72 de Cell.
    """
    floor_id: int
    name:     str
    grid:     list[list[Cell]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.grid:
            self.grid = [
                [Cell() for _ in range(GRID_SIZE)]
                for _ in range(GRID_SIZE)
            ]

    # ------------------------------------------------------------------
    # Accès par coordonnées centrées (x, y)
    # ------------------------------------------------------------------

    def get_cell(self, row: int, col: int) -> Cell:
        """Retourne la cellule à l'index (row, col)."""
        if not self._in_bounds(row, col):
            raise IndexError(f"Index ({row}, {col}) hors grille.")
        return self.grid[row][col]

    def set_cell(self, row: int, col: int, cell_type: CellType,
                 custom_image: Optional[str] = None) -> None:
        """Modifie la cellule à l'index (row, col)."""
        if not self._in_bounds(row, col):
            raise IndexError(f"Index ({row}, {col}) hors grille.")
        self.grid[row][col] = Cell(cell_type=cell_type, custom_image=custom_image)

    def get_cell_at(self, x: int, y: int) -> Cell:
        """Retourne la cellule aux coordonnées centrées (x, y)."""
        row, col = GridModel.coords_to_index(x, y)
        return self.get_cell(row, col)

    def set_cell_at(self, x: int, y: int, cell_type: CellType,
                    custom_image: Optional[str] = None) -> None:
        """Modifie la cellule aux coordonnées centrées (x, y)."""
        row, col = GridModel.coords_to_index(x, y)
        self.set_cell(row, col, cell_type, custom_image)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remet toutes les cellules à EMPTY."""
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                self.grid[row][col] = Cell()

    def count(self, cell_type: CellType) -> int:
        """Compte le nombre de cellules d'un type donné."""
        return sum(
            1
            for row in self.grid
            for cell in row
            if cell.cell_type == cell_type
        )

    def find_cells(self, cell_type: CellType) -> list[tuple[int, int]]:
        """Retourne la liste des (row, col) ayant le type donné."""
        return [
            (r, c)
            for r, row in enumerate(self.grid)
            for c, cell in enumerate(row)
            if cell.cell_type == cell_type
        ]

    def clone(self) -> "Floor":
        return Floor(
            floor_id=self.floor_id,
            name=self.name,
            grid=[[cell.clone() for cell in row] for row in self.grid],
        )

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    # ------------------------------------------------------------------
    # Sérialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id":   self.floor_id,
            "name": self.name,
            "grid": [[cell.to_dict() for cell in row] for row in self.grid],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Floor":
        grid = [
            [Cell.from_dict(cell_data) for cell_data in row]
            for row in data["grid"]
        ]
        return cls(
            floor_id=data["id"],
            name=data["name"],
            grid=grid,
        )


# ---------------------------------------------------------------------------
# GridModel
# ---------------------------------------------------------------------------

class GridModel:
    """Conteneur multi-étages et utilitaires de conversion de coordonnées.

    C'est le modèle racine de l'application. Il est sérialisé en JSON
    lors de l'export et reconstruit à l'import.

    Attributes:
        floors          : Liste ordonnée des étages.
        _active_floor_id: Identifiant de l'étage actuellement affiché.
        _next_id        : Compteur pour générer des IDs uniques.
    """

    def __init__(self) -> None:
        self.floors:           list[Floor] = []
        self._active_floor_id: int = -1
        self._next_id:         int = 1

    # ------------------------------------------------------------------
    # Gestion des étages
    # ------------------------------------------------------------------

    def add_floor(self, name: Optional[str] = None) -> Floor:
        """Crée et ajoute un nouvel étage vide. Retourne l'étage créé."""
        fid = self._next_id
        self._next_id += 1
        floor_name = name or f"Étage {fid}"
        floor = Floor(floor_id=fid, name=floor_name)
        self.floors.append(floor)
        if self._active_floor_id == -1:
            self._active_floor_id = fid
        return floor

    def remove_floor(self, floor_id: int) -> None:
        """Supprime un étage par son ID. Lève ValueError si introuvable."""
        idx = self._floor_index(floor_id)
        self.floors.pop(idx)
        if self._active_floor_id == floor_id:
            self._active_floor_id = self.floors[0].floor_id if self.floors else -1

    def get_floor(self, floor_id: int) -> Floor:
        """Retourne l'étage correspondant à floor_id."""
        return self.floors[self._floor_index(floor_id)]

    def get_active_floor(self) -> Optional[Floor]:
        """Retourne l'étage actif, ou None si aucun étage."""
        if self._active_floor_id == -1:
            return None
        return self.get_floor(self._active_floor_id)

    def set_active_floor(self, floor_id: int) -> None:
        self._floor_index(floor_id)  # Lève ValueError si inexistant
        self._active_floor_id = floor_id

    @property
    def active_floor_id(self) -> int:
        return self._active_floor_id

    @property
    def floor_count(self) -> int:
        return len(self.floors)

    def duplicate_floor(self, floor_id: int) -> Floor:
        """Clone un étage et l'insère juste après l'original.

        Le clone reçoit un nouvel ID unique et un nom suffixé " (copie)".
        Retourne le nouvel étage.
        """
        idx = self._floor_index(floor_id)
        source = self.floors[idx]
        new_id = self._next_id
        self._next_id += 1
        clone = source.clone()
        clone.floor_id = new_id
        clone.name = f"{source.name} (copie)"
        self.floors.insert(idx + 1, clone)
        return clone

    def rename_floor(self, floor_id: int, new_name: str) -> None:
        """Renomme un étage. Lève ValueError si introuvable.

        Le nom est strippé des espaces  une chaîne vide est refusée.
        """
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Le nom d'un étage ne peut pas être vide.")
        self.floors[self._floor_index(floor_id)].name = new_name

    def _floor_index(self, floor_id: int) -> int:
        for i, f in enumerate(self.floors):
            if f.floor_id == floor_id:
                return i
        raise ValueError(f"Aucun étage avec l'ID {floor_id}.")

    # ------------------------------------------------------------------
    # Conversion de coordonnées (méthodes statiques)
    # ------------------------------------------------------------------

    @staticmethod
    def coords_to_index(x: int, y: int) -> tuple[int, int]:
        """Convertit les coordonnées centrées (x, y) en index (row, col).

        Le système de coordonnées est :
          - x croît vers la droite  : x ∈ [-36, 35]
          - y croît vers le haut    : y ∈ [-36, 35]
          - (0, 0) = centre = index (36, 36)

        Formule :
          row = HALF - 1 - y  →  y= 35 → row= 0,  y=-36 → row=71
          col = HALF + x      →  x=-36 → col= 0,  x= 35 → col=71

          Domaine valide : x ∈ [-36, 35], y ∈ [-36, 35]
          Centre (0, 0) → row=35, col=36

        Raises:
            ValueError: si (x, y) est hors des limites.
        """
        row = HALF - 1 - y
        col = HALF + x
        if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
            raise ValueError(
                f"Coordonnées ({x}, {y}) hors limites "
                f"[{-HALF}, {HALF - 1}]."
            )
        return row, col

    @staticmethod
    def index_to_coords(row: int, col: int) -> tuple[int, int]:
        """Convertit un index (row, col) en coordonnées centrées (x, y).

        Inverse de coords_to_index.
        """
        x = col - HALF
        y = HALF - 1 - row
        return x, y

    @staticmethod
    def is_valid_coords(x: int, y: int) -> bool:
        """Retourne True si (x, y) est dans les limites de la grille."""
        return -HALF <= x <= HALF - 1 and -HALF <= y <= HALF - 1

    @staticmethod
    def is_valid_index(row: int, col: int) -> bool:
        """Retourne True si (row, col) est un index valide."""
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    # ------------------------------------------------------------------
    # État global
    # ------------------------------------------------------------------

    def clear_all(self) -> None:
        """Supprime tous les étages et réinitialise le modèle."""
        self.floors.clear()
        self._active_floor_id = -1
        self._next_id = 1

    def clone(self) -> "GridModel":
        """Retourne une copie profonde du modèle."""
        model = GridModel()
        model.floors = [f.clone() for f in self.floors]
        model._active_floor_id = self._active_floor_id
        model._next_id = self._next_id
        return model

    # ------------------------------------------------------------------
    # Sérialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "floors": [f.to_dict() for f in self.floors],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GridModel":
        model = cls()
        for floor_data in data.get("floors", []):
            floor = Floor.from_dict(floor_data)
            model.floors.append(floor)
            model._next_id = max(model._next_id, floor.floor_id + 1)
        if model.floors:
            model._active_floor_id = model.floors[0].floor_id
        return model

    def __repr__(self) -> str:
        return (
            f"GridModel({len(self.floors)} étage(s), "
            f"actif={self._active_floor_id})"
        )