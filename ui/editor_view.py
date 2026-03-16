"""
ui/editor_view.py
Canvas principal de l'éditeur — rendu de la grille 72×72.

Fonctionnalités :
  - Rendu QGraphicsView + QGraphicsScene (une QPixmap par étage)
  - Clic gauche : pose une cellule avec l'outil actif
  - Clic gauche + drag : dessin continu
  - Molette : zoom centré sur le curseur
  - Clic molette ou clic droit + drag : pan
  - Coordonnées en temps réel transmises via signal
"""

from __future__ import annotations

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

# Taille d'une cellule en pixels dans la QPixmap
CELL_PX = 16

# Couleur de la ligne de grille
GRID_LINE_COLOR = QColor(60, 60, 70, 180)

# Couleur de fond de la scène
SCENE_BG_COLOR = QColor(20, 20, 25)

# Outil gomme — même constante que dans main_window
TOOL_ERASER = "eraser"


# Coordonnées index de la case (0,0) — escalier d'entrée Godot
ORIGIN_ROW = HALF - 1   # 35
ORIGIN_COL = HALF       # 36

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
        cell_painted(x, y, type_value)  : cellule modifiée
    """

    cell_hovered = pyqtSignal(int, int)
    cell_painted = pyqtSignal(int, int, str)

    def __init__(self, model: GridModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self._active_tool: CellType | str = CellType.GROUND
        self._is_drawing = False       # drag en cours
        self._is_panning = False       # pan en cours
        self._pan_start = QPointF()    # position souris au début du pan
        self._zoom_factor = 1.0        # facteur de zoom courant

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

        # Premier rendu
        self.refresh()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_active_tool(self, tool: CellType | str) -> None:
        self._active_tool = tool

    @property
    def current_zoom(self) -> float:
        return self._zoom_factor

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
    # Rendu
    # ------------------------------------------------------------------

    def _render_floor(self, floor) -> QPixmap:
        """Génère la QPixmap complète de l'étage."""
        size = GRID_SIZE * CELL_PX
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(*CELL_COLORS[CellType.EMPTY]))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dessin de toutes les cellules
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                cell = floor.grid[row][col]
                if cell.cell_type != CellType.EMPTY:
                    self._draw_cell(painter, row, col, cell.cell_type)

        # Marqueur (0,0) — par-dessus les cellules, sous la grille
        self._draw_origin_marker(painter)

        # Lignes de grille
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(GRID_LINE_COLOR, 0.5))
        for i in range(GRID_SIZE + 1):
            painter.drawLine(i * CELL_PX, 0, i * CELL_PX, size)
            painter.drawLine(0, i * CELL_PX, size, i * CELL_PX)

        painter.end()
        return pixmap

    def _draw_cell(self, painter: QPainter, row: int, col: int,
                   cell_type: CellType) -> None:
        """Dessine une cellule : couleur pleine pour sol/mur, icône pour entités."""
        r, g, b = CELL_COLORS[cell_type]
        x = col * CELL_PX
        y = row * CELL_PX

        # Fond coloré
        painter.fillRect(x, y, CELL_PX, CELL_PX, QColor(r, g, b))

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

    def _draw_origin_marker(self, painter: QPainter) -> None:
        """Dessine le marqueur de la case (0,0) — origine du repère Godot."""
        x = ORIGIN_COL * CELL_PX
        y = ORIGIN_ROW * CELL_PX

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

        # Fond de la cellule
        r, g, b = CELL_COLORS[cell.cell_type]
        painter.fillRect(x, y, CELL_PX, CELL_PX, QColor(r, g, b))

        # Icône si cellule entité
        if cell.cell_type in CELL_ICONS:
            icon = CELL_ICONS[cell.cell_type]
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

        # Marqueur (0,0) si on repeint cette case précise
        if row == ORIGIN_ROW and col == ORIGIN_COL:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(QColor(255, 220, 0, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x + 1, y + 1, CELL_PX - 2, CELL_PX - 2)
            cx = x + CELL_PX // 2
            cy = y + CELL_PX // 2
            arm = max(2, CELL_PX // 4)
            painter.setPen(QPen(QColor(255, 220, 0, 200), 1))
            painter.drawLine(cx - arm, cy, cx + arm, cy)
            painter.drawLine(cx, cy - arm, cx, cy + arm)

        # Bords de grille
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

    def _paint_at(self, scene_pos: QPointF) -> None:
        """Pose ou efface une cellule à la position scène donnée."""
        rc = self._scene_pos_to_grid(scene_pos)
        if rc is None:
            return
        row, col = rc

        floor = self.model.get_active_floor()
        if floor is None:
            return

        if self._active_tool == TOOL_ERASER:
            cell_type = CellType.EMPTY
        else:
            cell_type = self._active_tool

        # Ne rien faire si la cellule est déjà du bon type
        if floor.grid[row][col].cell_type == cell_type:
            return

        floor.set_cell(row, col, cell_type)
        self._repaint_cell(row, col)

        x, y = GridModel.index_to_coords(row, col)
        self.cell_painted.emit(x, y, cell_type.value)

    # ------------------------------------------------------------------
    # Événements souris
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = True
            scene_pos = self.mapToScene(event.pos())
            self._paint_at(scene_pos)

        elif event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

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
            self._paint_at(scene_pos)

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
        elif event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

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