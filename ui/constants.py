"""
ui/constants.py
Constantes partagées entre les modules UI.
"""

# Outil gomme  identifiant UI uniquement, jamais stocké dans la grille
TOOL_ERASER = "eraser"

# Tailles de pinceau disponibles (en cellules, carré centré)
BRUSH_SIZES: list[int] = [1, 2, 3, 5]

# Taille de pinceau par défaut
BRUSH_SIZE_DEFAULT: int = 1

# Profondeur de l'historique undo/redo
UNDO_MAX_LEVELS: int = 20

# Raccourcis clavier par défaut -- format Qt key sequence string
# Touche simple : "E", "G", "Space"
# Combinaison   : "Ctrl+Z", "Ctrl+Y", "Shift+R"
DEFAULT_SHORTCUTS: dict[str, str] = {
    "eraser":          "E",
    "recenter":        "Space",
    "undo":            "Ctrl+Z",
    "redo":            "Ctrl+Y",
    "tool_ground":     "G",
    "tool_wall":       "W",
    "tool_enemy":      "N",
    "tool_boss":       "B",
    "tool_treasure":   "T",
    "tool_trap":       "P",
    "tool_camp":       "C",
    "tool_stairs_up":  "U",
    "tool_spawn":      "S",
}

# Labels lisibles pour la fenêtre Préférences
SHORTCUT_LABELS: dict[str, str] = {
    "eraser":          "Gomme",
    "recenter":        "Recentrer la vue",
    "undo":            "Annuler",
    "redo":            "Rétablir",
    "tool_ground":     "Outil : Sol",
    "tool_wall":       "Outil : Mur",
    "tool_enemy":      "Outil : Ennemi",
    "tool_boss":       "Outil : Boss",
    "tool_treasure":   "Outil : Trésor",
    "tool_trap":       "Outil : Piège",
    "tool_camp":       "Outil : Camp",
    "tool_stairs_up":  "Outil : Escalier haut",
    "tool_spawn":      "Outil : Spawn",
}