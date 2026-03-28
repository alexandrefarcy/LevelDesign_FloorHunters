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
    QPushButton, QLabel, QButtonGroup,
    QSizePolicy, QFrame, QScrollArea, QComboBox,
    QStatusBar, QFileDialog, QMessageBox, QInputDialog,
    QDialog, QTextEdit, QDialogButtonBox,
    QSlider, QSpinBox,
)
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut

from core.grid import CellType, GridModel, CELL_LABELS, CELL_COLORS, CELL_EMOJIS
from core.generator import Generator
from core.populator import Populator
from serialization.serializer import Serializer, SerializerError
from serialization.autosave import AutoSave
from ui.editor_view import EditorView
from ui.constants import TOOL_ERASER, BRUSH_SIZES, BRUSH_SIZE_DEFAULT


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

        # --- Taille de pinceau active ---
        self._active_brush_size: int = BRUSH_SIZE_DEFAULT

        # --- Chemin du fichier courant ---
        self._current_path: Path | None = None
        self._serializer = Serializer()

        # --- Construction de l'UI ---
        self._build_ui()
        self._refresh_floor_selector()
        self._update_status("Prêt  cliquez sur la grille pour dessiner.")

        # --- Autosave ---
        self._autosave = AutoSave(self.model, self._serializer)
        self._autosave.saved.connect(self._on_autosave_saved)
        self._autosave.failed.connect(self._on_autosave_failed)
        self._autosave.start()

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
        self.editor_view.cell_hovered_cleared.connect(self._on_cell_hovered_cleared)
        self.editor_view.cell_painted.connect(self._on_cell_painted)
        self.editor_view.tool_shortcut_requested.connect(self._on_tool_shortcut)

        # Raccourcis Ctrl+Z / Ctrl+Y
        QShortcut(QKeySequence.StandardKey.Undo, self).activated.connect(self._on_undo)
        QShortcut(QKeySequence.StandardKey.Redo, self).activated.connect(self._on_redo)
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

        # --- Boutons sprite personnalise ---
        sep_sprite = QFrame()
        sep_sprite.setFrameShape(QFrame.Shape.HLine)
        sep_sprite.setFrameShadow(QFrame.Shadow.Sunken)
        sep_sprite.setStyleSheet("color: #555555;")
        layout.addWidget(sep_sprite)

        btn_sprite = QPushButton("🖼 Sprite…")
        btn_sprite.setFixedSize(108, 30)
        btn_sprite.setToolTip(
            "Assigner une image personnalisee a l'outil actif"
        )
        btn_sprite.setStyleSheet(self._action_btn_style("#5a4a7a"))
        btn_sprite.clicked.connect(self._on_set_sprite)
        layout.addWidget(btn_sprite)

        btn_clear_sprite = QPushButton("✕ Sprite")
        btn_clear_sprite.setFixedSize(108, 30)
        btn_clear_sprite.setToolTip("Effacer le sprite personnalise de l'outil actif")
        btn_clear_sprite.setStyleSheet(self._action_btn_style("#5a3a3a"))
        btn_clear_sprite.clicked.connect(self._on_clear_sprite)
        layout.addWidget(btn_clear_sprite)

        return panel

    def _build_floor_toolbar(self) -> QWidget:
        """Construit la barre d'outils du haut -- deux lignes.

        Ligne 1 : Fichier | Etage (selector + actions) | Generer / Peupler
        Ligne 2 : Pinceau (QComboBox) | Zoom
        """
        bar = QWidget()
        bar.setFixedHeight(88)
        bar.setStyleSheet("background-color: #3c3c3c;")

        outer = QVBoxLayout(bar)
        outer.setContentsMargins(10, 4, 10, 4)
        outer.setSpacing(4)

        combo_style = """
            QComboBox {
                background: #555555;
                color: #ffffff;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #444444;
                color: #ffffff;
                selection-background-color: #4a6fa5;
            }
        """

        # ---- Ligne 1 : Fichier | Etage | Actions etage | Generer ----
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)

        def btn(label, color, slot, tooltip=""):
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setStyleSheet(self._action_btn_style(color))
            b.clicked.connect(slot)
            if tooltip:
                b.setToolTip(tooltip)
            return b

        row1.addWidget(btn("Nouveau",      "#444455", self._on_new_project))
        row1.addWidget(btn("Ouvrir...",    "#445566", self._on_open_project))
        row1.addWidget(btn("Enregistrer...", "#446644", self._on_save_project))

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        row1.addWidget(sep1)

        lbl_floor = QLabel("Etage :")
        lbl_floor.setStyleSheet("color: #cccccc; font-size: 12px;")
        row1.addWidget(lbl_floor)

        self.floor_selector = QComboBox()
        self.floor_selector.setFixedWidth(150)
        self.floor_selector.setStyleSheet(combo_style)
        self.floor_selector.currentIndexChanged.connect(self._on_floor_changed)
        row1.addWidget(self.floor_selector)

        row1.addWidget(btn("+ Ajouter",    "#4a7a4a", self._on_add_floor))
        row1.addWidget(btn("Supprimer",    "#7a4a4a", self._on_delete_floor))
        row1.addWidget(btn("Dupliquer",    "#4a5566", self._on_duplicate_floor))
        row1.addWidget(btn("Renommer...",  "#554a66", self._on_rename_floor))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        row1.addWidget(sep2)

        row1.addWidget(btn(
            "Generer", "#7a5a20", self._on_generate,
            "Genere les couloirs, murs et escaliers sur l'etage actif",
        ))
        row1.addWidget(btn(
            "Peupler", "#4a2a6a", self._on_populate,
            "Place automatiquement les entites sur l'etage actif",
        ))

        row1.addStretch()
        outer.addLayout(row1)

        # ---- Ligne 2 : Pinceau (combobox) | Zoom ----
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)

        lbl_brush = QLabel("Pinceau :")
        lbl_brush.setStyleSheet("color: #cccccc; font-size: 12px;")
        row2.addWidget(lbl_brush)

        self.brush_combo = QComboBox()
        self.brush_combo.setFixedWidth(90)
        self.brush_combo.setStyleSheet(combo_style)
        for size in BRUSH_SIZES:
            self.brush_combo.addItem(f"{size}x{size}", userData=size)
        default_idx = BRUSH_SIZES.index(BRUSH_SIZE_DEFAULT)
        self.brush_combo.setCurrentIndex(default_idx)
        self.brush_combo.currentIndexChanged.connect(self._on_brush_combo_changed)
        row2.addWidget(self.brush_combo)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setFrameShadow(QFrame.Shadow.Sunken)
        row2.addWidget(sep3)

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        row2.addWidget(self.zoom_label)

        btn_reset_zoom = QPushButton("Reinitialiser vue")
        btn_reset_zoom.setFixedHeight(28)
        btn_reset_zoom.setStyleSheet(self._action_btn_style("#555555"))
        btn_reset_zoom.clicked.connect(self._on_reset_zoom)
        row2.addWidget(btn_reset_zoom)

        row2.addStretch()
        outer.addLayout(row2)

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
    # Slots  outils
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def _on_brush_combo_changed(self, index: int) -> None:
        size = self.brush_combo.itemData(index)
        if size is not None:
            self._active_brush_size = size
            self.editor_view.set_brush_size(size)
            self._update_status(f"Pinceau : {size}x{size}")

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
    # Slots  étages
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
    def _on_duplicate_floor(self) -> None:
        active = self.model.get_active_floor()
        if active is None:
            return
        new_floor = self.model.duplicate_floor(active.floor_id)
        self._refresh_floor_selector()
        # Sélectionner le nouvel étage
        idx = next(
            i for i, f in enumerate(self.model.floors)
            if f.floor_id == new_floor.floor_id
        )
        self.floor_selector.setCurrentIndex(idx)
        self._update_status(f"Étage « {new_floor.name} » créé.")

    @pyqtSlot()
    def _on_rename_floor(self) -> None:
        active = self.model.get_active_floor()
        if active is None:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Renommer l'étage",
            "Nouveau nom :",
            text=active.name,
        )
        if not ok:
            return
        try:
            self.model.rename_floor(active.floor_id, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Nom invalide", str(exc))
            return
        self._refresh_floor_selector()
        self._update_status(f"Étage renommé : « {new_name.strip()} »")

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
    # Slots  canvas
    # ------------------------------------------------------------------

    @pyqtSlot(int, int)
    def _on_cell_hovered(self, x: int, y: int) -> None:
        self._update_status(f"Coordonnées : ({x}, {y})")

    @pyqtSlot()
    def _on_cell_hovered_cleared(self) -> None:
        self._update_status("Prêt  cliquez sur la grille pour dessiner.")

    @pyqtSlot()
    def _on_undo(self) -> None:
        if self.editor_view.undo():
            self._update_status("Annulé.")
            self._update_zoom_label()

    @pyqtSlot()
    def _on_redo(self) -> None:
        if self.editor_view.redo():
            self._update_status("Rétabli.")
            self._update_zoom_label()

    @pyqtSlot(str)
    def _on_tool_shortcut(self, tool_id: str) -> None:
        """Sélectionne l'outil via raccourci clavier (ex. E → gomme)."""
        for btn in self._tool_button_group.buttons():
            if btn.property("tool_id") == tool_id:
                btn.setChecked(True)
                break

    @pyqtSlot(int, int, str)
    def _on_cell_painted(self, x: int, y: int, cell_type_value: str) -> None:
        label = CELL_LABELS.get(CellType(cell_type_value), cell_type_value)
        self._update_status(f"Cellule ({x}, {y}) → {label}")
        self._update_zoom_label()

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Slots  fichier
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
        """Ouvre un projet complet (.tdp.json) ou un export Godot (.json)."""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un projet",
            str(self._current_path.parent if self._current_path else Path.home()),
            "Projet Tower Dungeon (*.tdp.json);;Export Godot (*.json);;Tous les fichiers (*)",
        )
        if not path_str:
            return
        path = Path(path_str)

        try:
            # Detecte le format selon l'extension
            if path.name.endswith(".tdp.json"):
                model = self._serializer.load_project(path)
                fmt = "projet"
            else:
                model = self._serializer.load(path)
                fmt = "export Godot"
        except SerializerError as exc:
            QMessageBox.critical(self, "Erreur d'ouverture", str(exc))
            return

        self.model = model
        self.editor_view.model = model
        self._autosave.set_model(model)
        self._current_path = path
        n = model.floor_count
        self.setWindowTitle(f"Tower Dungeon Level Editor  {path.name}")
        self._refresh_floor_selector()
        self.editor_view.refresh()
        self._update_status(
            f"Projet charge ({fmt}) : {path.name}  --  {n} etage(s)"
        )

    @pyqtSlot()
    def _on_save_project(self) -> None:
        """Enregistre le projet.

        Propose deux options :
          - Projet complet (.tdp.json) : tous les etages, rechargeable
          - Export Godot (.json)       : etage actif uniquement, pour Godot
        """
        # Choix du mode de sauvegarde
        dlg = QDialog(self)
        dlg.setWindowTitle("Enregistrer")
        dlg.setFixedSize(380, 160)
        dlg.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel("Que voulez-vous enregistrer ?")
        lbl.setStyleSheet("font-size: 12px; color: #dddddd;")
        layout.addWidget(lbl)

        btn_layout = QHBoxLayout()

        btn_project = QPushButton("Projet complet\n(tous les etages)")
        btn_project.setFixedHeight(48)
        btn_project.setStyleSheet(self._action_btn_style("#446644"))
        btn_project.clicked.connect(lambda: dlg.done(1))
        btn_layout.addWidget(btn_project)

        btn_godot = QPushButton("Export Godot\n(etage actif)")
        btn_godot.setFixedHeight(48)
        btn_godot.setStyleSheet(self._action_btn_style("#445566"))
        btn_godot.clicked.connect(lambda: dlg.done(2))
        btn_layout.addWidget(btn_godot)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(48)
        btn_cancel.setStyleSheet(self._action_btn_style("#555555"))
        btn_cancel.clicked.connect(lambda: dlg.done(0))
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)
        choice = dlg.exec()

        if choice == 0:
            return

        if choice == 1:
            # Sauvegarde projet complet
            default = str(
                self._current_path if (
                    self._current_path and self._current_path.name.endswith(".tdp.json")
                ) else Path.home() / "projet.tdp.json"
            )
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Enregistrer le projet complet",
                default,
                "Projet Tower Dungeon (*.tdp.json);;Tous les fichiers (*)",
            )
            if not path_str:
                return
            path = Path(path_str)
            if not path_str.endswith(".tdp.json"):
                path = Path(path_str + ".tdp.json") if not path_str.endswith(".json") \
                    else path.with_suffix("").with_suffix(".tdp.json")
            try:
                self._serializer.save_project(self.model, path)
            except SerializerError as exc:
                QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))
                return
            self._current_path = path
            n = self.model.floor_count
            self.setWindowTitle(f"Tower Dungeon Level Editor  {path.name}")
            self._update_status(
                f"Projet sauvegarde : {path.name}  --  {n} etage(s)"
            )

        else:
            # Export Godot etage actif
            default = str(
                self._current_path if (
                    self._current_path and not self._current_path.name.endswith(".tdp.json")
                ) else Path.home() / "level_1.json"
            )
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Exporter l'etage actif (Godot)",
                default,
                "Export Godot JSON (*.json);;Tous les fichiers (*)",
            )
            if not path_str:
                return
            path = Path(path_str)
            if not path_str.endswith(".json"):
                path = path.with_suffix(".json")
            try:
                self._serializer.save(self.model, path)
            except SerializerError as exc:
                QMessageBox.critical(self, "Erreur d'export", str(exc))
                return
            self._update_status(f"Export Godot : {path.name}")



    # ------------------------------------------------------------------
    # Slots  sprites personnalises
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_set_sprite(self) -> None:
        """Ouvre un dialog pour choisir une image et l'assigner a l'outil actif."""
        if self._active_tool == TOOL_ERASER:
            self._update_status("Impossible : la gomme n'a pas de sprite.")
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un sprite",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Tous les fichiers (*)",
        )
        if not path_str:
            return

        # Stocke le chemin relatif si possible, absolu sinon
        rel = self._serializer.make_relative(path_str)

        # Applique le sprite a toutes les cellules du type actif sur l'etage actif
        floor = self.model.get_active_floor()
        if floor is None:
            return

        from core.grid import GRID_SIZE as _GS
        count = 0
        for r in range(_GS):
            for c in range(_GS):
                cell = floor.grid[r][c]
                if cell.cell_type == self._active_tool:
                    cell.custom_image = rel
                    count += 1

        self.editor_view.refresh()
        tool_label = getattr(self._active_tool, "value",
                             str(self._active_tool))
        self._update_status(
            f"Sprite assigne a {count} cellule(s) '{tool_label}' : {Path(path_str).name}"
        )

    @pyqtSlot()
    def _on_clear_sprite(self) -> None:
        """Efface le sprite personnalise de toutes les cellules du type actif."""
        if self._active_tool == TOOL_ERASER:
            self._update_status("Impossible : la gomme n'a pas de sprite.")
            return

        floor = self.model.get_active_floor()
        if floor is None:
            return

        from core.grid import GRID_SIZE as _GS
        count = 0
        for r in range(_GS):
            for c in range(_GS):
                cell = floor.grid[r][c]
                if cell.cell_type == self._active_tool and cell.custom_image:
                    cell.custom_image = None
                    count += 1

        self.editor_view.refresh()
        tool_label = getattr(self._active_tool, "value",
                             str(self._active_tool))
        self._update_status(
            f"Sprite efface sur {count} cellule(s) '{tool_label}'."
        )

    # ------------------------------------------------------------------
    # Slots  peuplement d'entites
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_populate(self) -> None:
        """Ouvre le dialog de peuplement et lance le Populator."""
        floor = self.model.get_active_floor()
        if floor is None:
            QMessageBox.warning(self, "Aucun etage",
                                "Aucun etage actif.")
            return

        # Dialog de configuration des densites
        dlg = QDialog(self)
        dlg.setWindowTitle("Peupler l'etage")
        dlg.setFixedSize(400, 260)
        dlg.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Densites de peuplement")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0c060;")
        layout.addWidget(title)

        sliders: dict[str, QSlider] = {}
        labels:  dict[str, QLabel]  = {}

        def make_slider_row(label: str, key: str,
                            default: int, color: str) -> None:
            row = QHBoxLayout()
            lbl = QLabel(f"{label} :")
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
            row.addWidget(lbl)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 50)
            slider.setValue(default)
            slider.setFixedHeight(22)
            row.addWidget(slider)

            val_lbl = QLabel(f"{default}%")
            val_lbl.setFixedWidth(36)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            val_lbl.setStyleSheet("color: #cccccc; font-size: 12px;")
            row.addWidget(val_lbl)

            slider.valueChanged.connect(
                lambda v, l=val_lbl: l.setText(f"{v}%")
            )

            sliders[key] = slider
            labels[key]  = val_lbl
            layout.addLayout(row)

        make_slider_row("Ennemis",  "enemy",    20, "#e06060")
        make_slider_row("Tresors",  "treasure",  5, "#e0c040")
        make_slider_row("Pieges",   "trap",      15, "#e08030")

        note = QLabel(
            "Les entites existantes seront effacees avant le placement."
        )
        note.setStyleSheet("color: #888888; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("color: #ffffff;")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        enemy_d    = sliders["enemy"].value()    / 100.0
        treasure_d = sliders["treasure"].value() / 100.0
        trap_d     = sliders["trap"].value()     / 100.0

        pop = Populator()
        report = pop.run(
            floor,
            enemy_density=enemy_d,
            treasure_density=treasure_d,
            trap_density=trap_d,
        )

        self.editor_view.refresh()
        self._update_status(
            f"Peuplement : {report.enemies_placed} ennemis, "
            f"{report.treasures_placed} tresors, "
            f"{report.traps_placed} pieges."
        )
        self._show_population_report(report)

    def _show_population_report(self, report) -> None:
        """Affiche le rapport de peuplement dans un dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Rapport de peuplement")
        dlg.setMinimumSize(380, 260)
        dlg.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Resultat du peuplement")
        title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #c080ff;"
        )
        layout.addWidget(title)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet(
            "background-color: #1e1e1e; color: #cccccc; "
            "font-family: monospace; font-size: 12px; "
            "border: 1px solid #555555; border-radius: 4px;"
        )
        text.setPlainText(report.summary())
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.setStyleSheet("color: #ffffff;")
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)

        dlg.exec()

    # ------------------------------------------------------------------
    # Slots  generation procedurale
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_generate(self) -> None:
        """Lance le generateur procedural sur l'etage actif et affiche le rapport."""
        floor = self.model.get_active_floor()
        if floor is None:
            QMessageBox.warning(
                self,
                "Aucun etage",
                "Aucun etage actif. Ajoutez un etage avant de generer.",
            )
            return

        # Confirmation si l'etage contient deja des murs ou couloirs generés
        has_walls = any(
            floor.grid[r][c].cell_type.value == "wall"
            for r in range(72)
            for c in range(72)
        )
        if has_walls:
            reply = QMessageBox.question(
                self,
                "Regenerer ?",
                "L'etage contient deja des murs generes.\n"
                "Lancer la generation va ajouter couloirs et murs par-dessus.\n\n"
                "Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        gen = Generator()
        report = gen.run(floor)

        # Rafraichit le canvas pour afficher le resultat
        self.editor_view.refresh()
        self._update_status(
            f"Generation terminee : {report.rooms_kept} salles, "
            f"{report.corridors_traced} couloirs, "
            f"{report.transitions_added} transitions, "
            f"{report.walls_placed} murs."
        )

        # Affiche le rapport detaille
        self._show_generation_report(report)

    def _show_generation_report(self, report) -> None:
        """Affiche un dialog non-bloquant avec le rapport de generation."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Rapport de generation")
        dlg.setMinimumSize(420, 320)
        dlg.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Resultat de la generation procedurale")
        title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #f0c060;"
        )
        layout.addWidget(title)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet(
            "background-color: #1e1e1e; color: #cccccc; "
            "font-family: monospace; font-size: 12px; "
            "border: 1px solid #555555; border-radius: 4px;"
        )
        text.setPlainText(report.summary())
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.setStyleSheet("color: #ffffff;")
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)

        dlg.exec()

    # ------------------------------------------------------------------
    # Slots  autosave
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def _on_autosave_saved(self, path: str) -> None:
        """Affiche une confirmation discrete dans la barre de statut."""
        from pathlib import Path as _Path
        self.status_bar.showMessage(
            f"Autosave OK  --  {_Path(path).name}", 4000
        )

    @pyqtSlot(str)
    def _on_autosave_failed(self, error: str) -> None:
        """Affiche une alerte discrete en cas d'echec autosave."""
        self.status_bar.showMessage(f"Autosave echoue : {error}", 6000)

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