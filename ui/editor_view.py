"""
ui/editor_view.py
Canvas principal de l'éditeur  rendu de la grille 72×72.

Fonctionnalités :
  - Rendu QGraphicsView + QGraphicsScene (une QPixmap par étage)
  - Clic gauche : pose une cellule avec l'outil actif
  - Clic gauche + drag : dessin continu
  - Molette : zoom centré sur le curseur
  - Clic molette ou clic droit + drag : pan
  - Coordonnées en temps réel transmises via signal
"""

from __future__ import annotations

import copy
from collections import deque

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QFont,
    QWheelEvent, QMouseEvent,
)

from core.grid import (
    CellType, GridModel, GRID_SIZE, HALF,
    CELL_COLORS, CELL_LABELS,
)
from ui.constants import TOOL_ERASER, BRUSH_SIZES, BRUSH_SIZE_DEFAULT, UNDO_MAX_LEVELS

# Taille d'une cellule en pixels dans la QPixmap
CELL_PX = 16

# Couleur de la ligne de grille
GRID_LINE_COLOR = QColor(60, 60, 70, 180)

# Couleur de fond de la scène
SCENE_BG_COLOR = QColor(20, 20, 25)

# Coordonnées index de la case (0,0)  escalier d'entrée Godot
# Dérivées de GridModel pour rester en sync si la formule change
ORIGIN_ROW, ORIGIN_COL = GridModel.coords_to_index(0, 0)

# Icônes Unicode pour les cellules entités
CELL_ICONS: dict[CellType, str] = {
    CellType.ENEMY:       "☠",
    CellType.BOSS:        "★",
    CellType.TREASURE:    "◆",
    CellType.TRAP:        "▲",
    CellType.CAMP:        "◉",
    CellType.STAIRS_DOWN: "↧",
    CellType.STAIRS_UP:   "↥",
    CellType.SPAWN:       "◎",
}


class EditorView(QGraphicsView):
    """Vue principale de l'éditeur de grille.

    Signals:
        cell_hovered(x, y)              : coordonnées centrées survolées
        cell_hovered_cleared()          : curseur sorti de la grille
        cell_painted(x, y, type_value)  : cellule modifiée
    """

    cell_hovered = pyqtSignal(int, int)
    cell_hovered_cleared = pyqtSignal()
    cell_painted = pyqtSignal(int, int, str)
    tool_shortcut_requested = pyqtSignal(str)  # émis quand E pressé → TOOL_ERASER

    def __init__(self, model: GridModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self._active_tool: CellType | str = CellType.GROUND
        self._brush_size: int = BRUSH_SIZE_DEFAULT
        self._is_drawing = False       # drag en cours
        self._is_panning = False       # pan en cours
        self._pan_start = QPointF()    # position souris au début du pan
        self._zoom_factor = 1.0        # facteur de zoom courant

        # Historique undo/redo  snapshots de grille par coup de pinceau
        self._undo_stack: deque[list[list]] = deque(maxlen=UNDO_MAX_LEVELS)
        self._redo_stack: deque[list[list]] = deque(maxlen=UNDO_MAX_LEVELS)
        self._snapshot_before: list[list] | None = None  # snapshot au mousePress

        # --- Scène ---
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(SCENE_BG_COLOR))
        self.setScene(self._scene)

        # Item pixmap qui contient le rendu de la grille
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        # --- Configuration de la vue ---
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # reçoit les touches clavier

        # Premier rendu
        self.refresh()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_active_tool(self, tool: CellType | str) -> None:
        self._active_tool = tool

    def set_brush_size(self, size: int) -> None:
        """Définit la taille du pinceau (doit être dans BRUSH_SIZES)."""
        if size in BRUSH_SIZES:
            self._brush_size = size

    @property
    def brush_size(self) -> int:
        return self._brush_size

    @property
    def current_zoom(self) -> float:
        return self._zoom_factor

    def undo(self) -> bool:
        """Annule le dernier coup de pinceau. Retourne True si undo effectué."""
        if not self._undo_stack:
            return False
        floor = self.model.get_active_floor()
        if floor is None:
            return False
        # Sauvegarde l'état courant dans redo
        self._redo_stack.append(self._clone_grid(floor))
        # Restaure l'état précédent
        self._restore_grid(floor, self._undo_stack.pop())
        self.refresh()
        return True

    def redo(self) -> bool:
        """Rétablit le dernier coup de pinceau annulé. Retourne True si redo effectué."""
        if not self._redo_stack:
            return False
        floor = self.model.get_active_floor()
        if floor is None:
            return False
        self._undo_stack.append(self._clone_grid(floor))
        self._restore_grid(floor, self._redo_stack.pop())
        self.refresh()
        return True

    def refresh(self) -> None:
        """Redessine entièrement la pixmap depuis le modèle actif."""
        floor = self.model.get_active_floor()
        if floor is None:
            return
        pixmap = self._render_floor(floor)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

    def reset_zoom(self) -> None:
        """Remet le zoom à 100% et centre la vue."""
        self.resetTransform()
        self._zoom_factor = 1.0
        self.centerOn(self._pixmap_item)

    # ------------------------------------------------------------------
    # Utilitaires undo/redo
    # ------------------------------------------------------------------

    def _clone_grid(self, floor) -> list[list]:
        """Retourne une copie profonde de la grille de l'étage."""
        return copy.deepcopy(floor.grid)

    def _restore_grid(self, floor, grid_snapshot: list[list]) -> None:
        """Restaure la grille d'un étage depuis un snapshot."""
        floor.grid = grid_snapshot

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def _render_floor(self, floor) -> QPixmap:
        """Génère la QPixmap complète de l'étage."""
        size = GRID_SIZE * CELL_PX
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(*CELL_COLORS[CellType.EMPTY]))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dessin de toutes les cellules non-vides
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                cell = floor.grid[row][col]
                if cell.cell_type != CellType.EMPTY:
                    self._draw_cell_on_painter(painter, row, col, cell.cell_type)

        # Marqueur (0,0)  par-dessus les cellules, sous la grille
        self._draw_origin_marker_on_painter(painter)

        # Lignes de grille (par-dessus tout)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(GRID_LINE_COLOR, 0.5))
        for i in range(GRID_SIZE + 1):
            painter.drawLine(i * CELL_PX, 0, i * CELL_PX, size)
            painter.drawLine(0, i * CELL_PX, size, i * CELL_PX)

        painter.end()
        return pixmap

    def _draw_cell_on_painter(self, painter: QPainter, row: int, col: int,
                               cell_type: CellType) -> None:
        """Dessine une cellule : couleur pleine pour sol/mur, icône pour entités.

        Si la cellule a un custom_image valide, l'image remplace l'icône Unicode.
        Méthode commune utilisée par _render_floor et _repaint_cell
        pour éviter toute duplication.
        """
        floor = self.model.get_active_floor()
        r, g, b = CELL_COLORS[cell_type]
        x = col * CELL_PX
        y = row * CELL_PX

        # Fond coloré
        painter.fillRect(x, y, CELL_PX, CELL_PX, QColor(r, g, b))

        # Sprite personnalisé si disponible
        custom_image = None
        if floor is not None:
            cell = floor.grid[row][col]
            custom_image = cell.custom_image

        if custom_image:
            from pathlib import Path as _Path
            img_path = _Path(custom_image)
            if img_path.exists():
                sprite = QPixmap(str(img_path))
                if not sprite.isNull():
                    painter.drawPixmap(x, y, CELL_PX, CELL_PX, sprite)
                    return
            # Chemin invalide : on tombe en fallback icone/couleur

        # Icône pour les cellules entités (tout sauf GROUND et WALL)
        if cell_type in CELL_ICONS:
            icon = CELL_ICONS[cell_type]
            font = QFont()
            font.setPixelSize(max(8, CELL_PX - 4))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(
                x, y, CELL_PX, CELL_PX,
                Qt.AlignmentFlag.AlignCenter,
                icon,
            )

    def _draw_origin_marker_on_painter(self, painter: QPainter) -> None:
        """Dessine le marqueur de la case (0,0)  origine du repère Godot."""
        x = ORIGIN_COL * CELL_PX
        y = ORIGIN_ROW * CELL_PX

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Bordure jaune vive sur les 4 côtés de la case
        painter.setPen(QPen(QColor(255, 220, 0, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(x + 1, y + 1, CELL_PX - 2, CELL_PX - 2)

        # Petit "+" centré dans la case
        cx = x + CELL_PX // 2
        cy = y + CELL_PX // 2
        arm = max(2, CELL_PX // 4)
        painter.setPen(QPen(QColor(255, 220, 0, 200), 1))
        painter.drawLine(cx - arm, cy, cx + arm, cy)
        painter.drawLine(cx, cy - arm, cx, cy + arm)

    def _repaint_cell(self, row: int, col: int) -> None:
        """Redessine uniquement la cellule (row, col) dans la pixmap existante."""
        floor = self.model.get_active_floor()
        if floor is None:
            return

        pixmap = self._pixmap_item.pixmap()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cell = floor.grid[row][col]
        x = col * CELL_PX
        y = row * CELL_PX

        # Toujours effacer d'abord avec la couleur EMPTY pour éviter les
        # résidus visuels (notamment le marqueur (0,0) sur fond vide)
        painter.fillRect(x, y, CELL_PX, CELL_PX,
                         QColor(*CELL_COLORS[CellType.EMPTY]))

        # Dessin de la cellule si non-vide
        if cell.cell_type != CellType.EMPTY:
            self._draw_cell_on_painter(painter, row, col, cell.cell_type)

        # Marqueur (0,0) si on repeint cette case précise
        if row == ORIGIN_ROW and col == ORIGIN_COL:
            self._draw_origin_marker_on_painter(painter)

        # Bords de grille (par-dessus tout)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(GRID_LINE_COLOR, 0.5))
        painter.drawRect(x, y, CELL_PX, CELL_PX)

        painter.end()
        self._pixmap_item.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # Conversion scène → grille
    # ------------------------------------------------------------------

    def _scene_pos_to_grid(self, scene_pos: QPointF) -> tuple[int, int] | None:
        """Convertit une position scène en (row, col). Retourne None si hors grille."""
        col = int(scene_pos.x() / CELL_PX)
        row = int(scene_pos.y() / CELL_PX)
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            return row, col
        return None

    # ------------------------------------------------------------------
    # Pose d'une cellule
    # ------------------------------------------------------------------

    def _paint_brush(self, scene_pos: QPointF) -> None:
        """Pose ou efface un carré de cellules centré sur la position scène."""
        rc = self._scene_pos_to_grid(scene_pos)
        if rc is None:
            return
        center_row, center_col = rc

        floor = self.model.get_active_floor()
        if floor is None:
            return

        cell_type = CellType.EMPTY if self._active_tool == TOOL_ERASER \
            else self._active_tool

        half = self._brush_size // 2
        painted_any = False

        for dr in range(-half, self._brush_size - half):
            for dc in range(-half, self._brush_size - half):
                row = center_row + dr
                col = center_col + dc
                if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
                    continue
                if floor.grid[row][col].cell_type == cell_type:
                    continue
                floor.set_cell(row, col, cell_type)
                self._repaint_cell(row, col)
                painted_any = True

        if painted_any:
            # Émet le signal sur la cellule centrale uniquement
            x, y = GridModel.index_to_coords(center_row, center_col)
            self.cell_painted.emit(x, y, cell_type.value)

    # ------------------------------------------------------------------
    # Événements souris
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = True
            # Snapshot de la grille avant le coup de pinceau (pour undo)
            floor = self.model.get_active_floor()
            if floor is not None:
                self._snapshot_before = self._clone_grid(floor)
            self._redo_stack.clear()  # un nouveau dessin invalide le redo
            scene_pos = self.mapToScene(event.pos())
            self._paint_brush(scene_pos)
        elif event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        scene_pos = self.mapToScene(event.pos())

        # Coordonnées centrées pour la barre de statut
        rc = self._scene_pos_to_grid(scene_pos)
        if rc is not None:
            row, col = rc
            x, y = GridModel.index_to_coords(row, col)
            self.cell_hovered.emit(x, y)

        # Dessin par drag
        if self._is_drawing:
            self._paint_brush(scene_pos)

        # Pan
        if self._is_panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = False
            # Push le snapshot pré-dessin dans l'undo stack
            if self._snapshot_before is not None:
                self._undo_stack.append(self._snapshot_before)
                self._snapshot_before = None
        elif event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        """Notifie main_window que le curseur a quitté la grille."""
        self.cell_hovered_cleared.emit()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        """Raccourcis clavier gérés directement sur le canvas."""
        key = event.key()
        if key == Qt.Key.Key_E:
            self.tool_shortcut_requested.emit(TOOL_ERASER)
        elif key == Qt.Key.Key_Space:
            self.reset_zoom()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Zoom molette
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
        else:
            factor = zoom_out_factor

        new_zoom = self._zoom_factor * factor

        # Limites de zoom : 20% à 800%
        if 0.2 <= new_zoom <= 8.0:
            self._zoom_factor = new_zoom
            self.scale(factor, factor)