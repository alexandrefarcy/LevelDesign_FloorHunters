"""
ui/constants.py
Constantes partagées entre les modules UI.
"""

# Outil gomme — identifiant UI uniquement, jamais stocké dans la grille
TOOL_ERASER = "eraser"

# Tailles de pinceau disponibles (en cellules, carré centré)
BRUSH_SIZES: list[int] = [1, 2, 3, 5]

# Taille de pinceau par défaut
BRUSH_SIZE_DEFAULT: int = 1

# Profondeur de l'historique undo/redo
UNDO_MAX_LEVELS: int = 20