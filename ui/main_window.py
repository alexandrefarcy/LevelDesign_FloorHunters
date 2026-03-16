"""
ui/main_window.py
Fenêtre principale du Tower Dungeon Level Editor.

Contient :
  - MainWindow : fenêtre principale QMainWindow
    - Toolbar gauche  : palette des outils (CellType)
    - Toolbar haute   : sélecteur d'étages + boutons Ajouter/Supprimer
    - Zone centrale   : EditorView (canvas PyQt6)
    - Barre de statut : coordonnées en temps réel
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QToolButton, QButtonGroup,
    QSizePolicy, QFrame, QScrollArea, QComboBox,
    QStatusBar, QFileDialog, QMessageBox,
)
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont

from core.grid import CellType, GridModel, CELL_LABELS, CELL_COLORS, CELL_EMOJIS
from serialization.serializer import Serializer, SerializerError
from ui.editor_view import EditorView


# Outil gomme — identifiant UI uniquement, jamais stocké dans la grille
TOOL_ERASER = "eraser"


class MainWindow(QMainWindow):
    """Fenêtre principale de l'éditeur."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tower Dungeon Level Editor")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)

        # --- Modèle de données ---
        self.model = GridModel()
        self.model.add_floor("Étage 1")

        # --- Outil actif (CellType ou TOOL_ERASER) ---
        self._active_tool: CellType | str = CellType.GROUND

        # --- Chemin du fichier courant ---
        self._current_path: Path | None = None
        self._serializer = Serializer()

        # --- Construction de l'UI ---
        self._build_ui()
        self._refresh_floor_selector()
        self._update_status("Prêt — cliquez sur la grille pour dessiner.")

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble tous les widgets de la fenêtre."""

        # Widget central conteneur
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Panneau gauche : palette d'outils ---
        left_panel = self._build_tool_palette()
        main_layout.addWidget(left_panel)

        # Séparateur vertical
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(sep)

        # --- Zone droite : toolbar étages + canvas ---
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        floor_bar = self._build_floor_toolbar()
        right_layout.addWidget(floor_bar)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(sep2)

        # Canvas éditeur
        self.editor_view = EditorView(self.model, parent=self)
        self.editor_view.cell_hovered.connect(self._on_cell_hovered)
        self.editor_view.cell_painted.connect(self._on_cell_painted)
        right_layout.addWidget(self.editor_view, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget, stretch=1)

        # --- Barre de statut ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_tool_palette(self) -> QWidget:
        """Construit le panneau gauche avec les boutons d'outils."""
        panel = QWidget()
        panel.setFixedWidth(120)
        panel.setStyleSheet("background-color: #2b2b2b;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(4)

        title = QLabel("Outils")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #aaaaaa; font-size: 11px; font-weight: bold;")
        layout.addWidget(title)

        self._tool_button_group = QButtonGroup(self)
        self._tool_button_group.setExclusive(True)

        # Boutons pour chaque CellType (sauf EMPTY qui n'est pas un outil)
        tools: list[tuple[CellType | str, str, str]] = [
            (CellType.GROUND,      CELL_EMOJIS[CellType.GROUND],      CELL_LABELS[CellType.GROUND]),
            (CellType.WALL,        CELL_EMOJIS[CellType.WALL],        CELL_LABELS[CellType.WALL]),
            (CellType.STAIRS_UP,   CELL_EMOJIS[CellType.STAIRS_UP],   CELL_LABELS[CellType.STAIRS_UP]),
            (CellType.SPAWN,       CELL_EMOJIS[CellType.SPAWN],       CELL_LABELS[CellType.SPAWN]),
            (CellType.ENEMY,       CELL_EMOJIS[CellType.ENEMY],       CELL_LABELS[CellType.ENEMY]),
            (CellType.BOSS,        CELL_EMOJIS[CellType.BOSS],        CELL_LABELS[CellType.BOSS]),
            (CellType.TREASURE,    CELL_EMOJIS[CellType.TREASURE],    CELL_LABELS[CellType.TREASURE]),
            (CellType.TRAP,        CELL_EMOJIS[CellType.TRAP],        CELL_LABELS[CellType.TRAP]),
            (CellType.CAMP,        CELL_EMOJIS[CellType.CAMP],        CELL_LABELS[CellType.CAMP]),
            (TOOL_ERASER,          "🗑️",                              "Gomme"),
        ]

        for tool_id, emoji, label in tools:
            btn = QToolButton()
            btn.setText(f"{emoji}\n{label}")
            btn.setCheckable(True)
            btn.setFixedSize(108, 52)
            btn.setToolTip(label)
            btn.setStyleSheet(self._tool_btn_style(active=False))
            btn.setProperty("tool_id", tool_id)

            # Ground sélectionné par défaut
            if tool_id == CellType.GROUND:
                btn.setChecked(True)
                btn.setStyleSheet(self._tool_btn_style(active=True))

            btn.toggled.connect(lambda checked, b=btn: self._on_tool_toggled(checked, b))
            self._tool_button_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch()
        return panel

    def _build_floor_toolbar(self) -> QWidget:
        """Construit la barre d'outils du haut pour la gestion des étages."""
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background-color: #3c3c3c;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        # Boutons fichier
        btn_new = QPushButton("Nouveau")
        btn_new.setFixedHeight(30)
        btn_new.setStyleSheet(self._action_btn_style("#444455"))
        btn_new.clicked.connect(self._on_new_project)
        layout.addWidget(btn_new)

        btn_open = QPushButton("Ouvrir…")
        btn_open.setFixedHeight(30)
        btn_open.setStyleSheet(self._action_btn_style("#445566"))
        btn_open.clicked.connect(self._on_open_project)
        layout.addWidget(btn_open)

        btn_save = QPushButton("Enregistrer…")
        btn_save.setFixedHeight(30)
        btn_save.setStyleSheet(self._action_btn_style("#446644"))
        btn_save.clicked.connect(self._on_save_project)
        layout.addWidget(btn_save)

        sep_file = QFrame()
        sep_file.setFrameShape(QFrame.Shape.VLine)
        sep_file.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep_file)

        lbl = QLabel("Étage :")
        lbl.setStyleSheet("color: #cccccc; font-size: 12px;")
        layout.addWidget(lbl)

        self.floor_selector = QComboBox()
        self.floor_selector.setFixedWidth(160)
        self.floor_selector.setStyleSheet("""
            QComboBox {
                background: #555555;
                color: #ffffff;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
        """)
        self.floor_selector.currentIndexChanged.connect(self._on_floor_changed)
        layout.addWidget(self.floor_selector)

        btn_add = QPushButton("+ Ajouter")
        btn_add.setFixedHeight(30)
        btn_add.setStyleSheet(self._action_btn_style("#4a7a4a"))
        btn_add.clicked.connect(self._on_add_floor)
        layout.addWidget(btn_add)

        btn_del = QPushButton("🗑 Supprimer")
        btn_del.setFixedHeight(30)
        btn_del.setStyleSheet(self._action_btn_style("#7a4a4a"))
        btn_del.clicked.connect(self._on_delete_floor)
        layout.addWidget(btn_del)

        layout.addStretch()

        # Indicateur zoom
        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(self.zoom_label)

        btn_reset_zoom = QPushButton("Réinitialiser vue")
        btn_reset_zoom.setFixedHeight(30)
        btn_reset_zoom.setStyleSheet(self._action_btn_style("#555555"))
        btn_reset_zoom.clicked.connect(self._on_reset_zoom)
        layout.addWidget(btn_reset_zoom)

        return bar

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_btn_style(active: bool) -> str:
        bg = "#4a6fa5" if active else "#3c3c3c"
        border = "#7aafff" if active else "#555555"
        return f"""
            QToolButton {{
                background-color: {bg};
                color: #ffffff;
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 11px;
                padding: 2px;
            }}
            QToolButton:hover {{
                background-color: #5a7fb5;
                border: 1px solid #9acfff;
            }}
        """

    @staticmethod
    def _action_btn_style(bg_color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #888888; }}
            QPushButton:pressed {{ background-color: #333333; }}
        """

    # ------------------------------------------------------------------
    # Slots — outils
    # ------------------------------------------------------------------

    @pyqtSlot(bool)
    def _on_tool_toggled(self, checked: bool, btn: QToolButton) -> None:
        if checked:
            tool_id = btn.property("tool_id")
            self._active_tool = tool_id
            btn.setStyleSheet(self._tool_btn_style(active=True))
            # Mettre à jour le style des autres boutons
            for b in self._tool_button_group.buttons():
                if b is not btn:
                    b.setStyleSheet(self._tool_btn_style(active=False))
            # Transmettre l'outil au canvas
            self.editor_view.set_active_tool(tool_id)
            label = btn.toolTip()
            self._update_status(f"Outil sélectionné : {label}")

    # ------------------------------------------------------------------
    # Slots — étages
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_add_floor(self) -> None:
        n = self.model.floor_count + 1
        floor = self.model.add_floor(f"Étage {n}")
        self._refresh_floor_selector()
        # Sélectionner le nouvel étage
        idx = next(
            i for i, f in enumerate(self.model.floors)
            if f.floor_id == floor.floor_id
        )
        self.floor_selector.setCurrentIndex(idx)
        self._update_status(f"Étage « {floor.name} » créé.")

    @pyqtSlot()
    def _on_delete_floor(self) -> None:
        if self.model.floor_count <= 1:
            self._update_status("Impossible : le projet doit avoir au moins un étage.")
            return
        active = self.model.get_active_floor()
        if active:
            self.model.remove_floor(active.floor_id)
            self._refresh_floor_selector()
            self.editor_view.refresh()
            self._update_status(f"Étage supprimé.")

    @pyqtSlot(int)
    def _on_floor_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.model.floors):
            return
        floor = self.model.floors[index]
        self.model.set_active_floor(floor.floor_id)
        self.editor_view.refresh()
        self._update_status(f"Étage actif : {floor.name}")

    @pyqtSlot()
    def _on_reset_zoom(self) -> None:
        self.editor_view.reset_zoom()

    # ------------------------------------------------------------------
    # Slots — canvas
    # ------------------------------------------------------------------

    @pyqtSlot(int, int)
    def _on_cell_hovered(self, x: int, y: int) -> None:
        self._update_status(f"Coordonnées : ({x}, {y})")

    @pyqtSlot(int, int, str)
    def _on_cell_painted(self, x: int, y: int, cell_type_value: str) -> None:
        label = CELL_LABELS.get(CellType(cell_type_value), cell_type_value)
        self._update_status(f"Cellule ({x}, {y}) → {label}")
        self._update_zoom_label()

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Slots — fichier
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_new_project(self) -> None:
        reply = QMessageBox.question(
            self,
            "Nouveau projet",
            "Créer un nouveau projet ? Les modifications non sauvegardées seront perdues.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.model.clear_all()
        self.model.add_floor("Étage 1")
        self._current_path = None
        self.setWindowTitle("Tower Dungeon Level Editor")
        self._refresh_floor_selector()
        self.editor_view.refresh()
        self._update_status("Nouveau projet créé.")

    @pyqtSlot()
    def _on_open_project(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un projet",
            str(self._current_path.parent if self._current_path else Path.home()),
            "Tower Dungeon JSON (*.json);;Tous les fichiers (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            model = self._serializer.load(path)
        except SerializerError as exc:
            QMessageBox.critical(self, "Erreur d'ouverture", str(exc))
            return
        self.model = model
        self.editor_view.model = model
        self._current_path = path
        self.setWindowTitle(f"Tower Dungeon Level Editor — {path.name}")
        self._refresh_floor_selector()
        self.editor_view.refresh()
        self._update_status(f"Projet chargé : {path.name}")

    @pyqtSlot()
    def _on_save_project(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le projet",
            str(self._current_path if self._current_path else Path.home() / "projet.json"),
            "Tower Dungeon JSON (*.json);;Tous les fichiers (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path_str.endswith(".json"):
            path = path.with_suffix(".json")
        try:
            self._serializer.save(self.model, path)
        except SerializerError as exc:
            QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))
            return
        self._current_path = path
        self.setWindowTitle(f"Tower Dungeon Level Editor — {path.name}")
        self._update_status(f"Projet sauvegardé : {path.name}")

    def _refresh_floor_selector(self) -> None:
        """Resynchronise le sélecteur d'étages avec le modèle."""
        self.floor_selector.blockSignals(True)
        self.floor_selector.clear()
        for floor in self.model.floors:
            self.floor_selector.addItem(floor.name, userData=floor.floor_id)
        # Sélectionner l'étage actif
        active_id = self.model.active_floor_id
        for i, floor in enumerate(self.model.floors):
            if floor.floor_id == active_id:
                self.floor_selector.setCurrentIndex(i)
                break
        self.floor_selector.blockSignals(False)

    def _update_status(self, message: str) -> None:
        self.status_bar.showMessage(message)

    def _update_zoom_label(self) -> None:
        if hasattr(self, "editor_view"):
            pct = int(self.editor_view.current_zoom * 100)
            self.zoom_label.setText(f"Zoom: {pct}%")