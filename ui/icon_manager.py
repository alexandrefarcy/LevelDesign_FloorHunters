"""
ui/icon_manager.py
Gestion des icones personnalisees -- copie PNG, dialog creation/gestion.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QListWidget,
    QListWidgetItem, QDialogButtonBox, QColorDialog,
    QTabWidget, QWidget, QComboBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QIcon

from core.grid import (
    CellType, CELL_LABELS, CELL_COLORS,
    CustomCellDef, CUSTOM_REGISTRY,
)

ICONS_DIR = Path.home() / ".tower_dungeon" / "icons"


# ---------------------------------------------------------------------------
# Utilitaire -- copie PNG
# ---------------------------------------------------------------------------

def import_png(src_path: str) -> str:
    """Copie un PNG dans ~/.tower_dungeon/icons/ et retourne le chemin absolu."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
    dest = ICONS_DIR / src.name
    # Eviter les collisions de noms
    counter = 1
    while dest.exists():
        dest = ICONS_DIR / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    shutil.copy2(src, dest)
    return str(dest)


# ---------------------------------------------------------------------------
# Dialog -- Nouvelle icone custom (nouvel outil)
# ---------------------------------------------------------------------------

class NewCustomTypeDialog(QDialog):
    """Dialog de création d'un nouveau type de cellule custom."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouvelle icone -- Nouvel outil")
        self.setMinimumSize(420, 360)
        self.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")
        self._color = (100, 100, 120)
        self._png_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Créer un nouvel outil personnalisé")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #aaccff;")
        layout.addWidget(title)

        # Nom (type_id)
        row_id = QHBoxLayout()
        row_id.addWidget(QLabel("Identifiant JSON :"))
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("ex: garde  (minuscules, sans espace)")
        self._id_edit.setStyleSheet(self._field_style())
        row_id.addWidget(self._id_edit)
        layout.addLayout(row_id)

        # Label
        row_lbl = QHBoxLayout()
        row_lbl.addWidget(QLabel("Nom affiché :"))
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("ex: Garde")
        self._label_edit.setStyleSheet(self._field_style())
        row_lbl.addWidget(self._label_edit)
        layout.addLayout(row_lbl)

        # Icone Unicode
        row_uni = QHBoxLayout()
        row_uni.addWidget(QLabel("Icone Unicode :"))
        self._unicode_edit = QLineEdit()
        self._unicode_edit.setPlaceholderText("ex: ⚔")
        self._unicode_edit.setMaxLength(4)
        self._unicode_edit.setFixedWidth(60)
        self._unicode_edit.setStyleSheet(self._field_style())
        row_uni.addWidget(self._unicode_edit)
        row_uni.addStretch()
        layout.addLayout(row_uni)

        # PNG
        row_png = QHBoxLayout()
        self._png_label = QLabel("Aucun PNG sélectionné")
        self._png_label.setStyleSheet("color: #888888; font-size: 11px;")
        row_png.addWidget(self._png_label)
        btn_png = QPushButton("Choisir PNG...")
        btn_png.setFixedHeight(28)
        btn_png.setStyleSheet(self._btn_style("#445566"))
        btn_png.clicked.connect(self._on_pick_png)
        row_png.addWidget(btn_png)
        layout.addLayout(row_png)

        # Couleur de fond
        row_col = QHBoxLayout()
        row_col.addWidget(QLabel("Couleur de fond :"))
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(32, 24)
        self._update_color_preview()
        row_col.addWidget(self._color_preview)
        btn_col = QPushButton("Choisir...")
        btn_col.setFixedHeight(28)
        btn_col.setStyleSheet(self._btn_style("#445566"))
        btn_col.clicked.connect(self._on_pick_color)
        row_col.addWidget(btn_col)
        row_col.addStretch()
        layout.addLayout(row_col)

        layout.addStretch()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("color: #ffffff;")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_pick_png(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image PNG", "", "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self._png_path = path
            self._png_label.setText(Path(path).name)
            self._png_label.setStyleSheet("color: #88cc88; font-size: 11px;")

    def _on_pick_color(self) -> None:
        r, g, b = self._color
        initial = QColor(r, g, b)
        color = QColorDialog.getColor(initial, self, "Choisir une couleur")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue())
            self._update_color_preview()

    def _update_color_preview(self) -> None:
        r, g, b = self._color
        self._color_preview.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #777;"
        )

    def _on_accept(self) -> None:
        type_id = self._id_edit.text().strip().lower().replace(" ", "_")
        label = self._label_edit.text().strip()

        if not type_id:
            QMessageBox.warning(self, "Champ requis", "L'identifiant JSON est obligatoire.")
            return
        if not type_id.isidentifier():
            QMessageBox.warning(self, "Identifiant invalide",
                "L'identifiant ne doit contenir que des lettres, chiffres et _.")
            return
        # Vérifier conflit avec CellType existants
        existing = [ct.value for ct in CellType]
        if type_id in existing:
            QMessageBox.warning(self, "Conflit",
                f"'{type_id}' est déjà un type natif. Choisissez un autre identifiant.")
            return
        if not label:
            label = type_id.capitalize()

        icon_unicode = self._unicode_edit.text().strip() or "?"
        icon_path = None
        if self._png_path:
            try:
                icon_path = import_png(self._png_path)
            except OSError as e:
                QMessageBox.warning(self, "Erreur PNG", f"Impossible de copier le PNG :\n{e}")

        defn = CustomCellDef(
            type_id=type_id,
            label=label,
            color=self._color,
            icon_unicode=icon_unicode,
            icon_path=icon_path,
        )
        CUSTOM_REGISTRY.register(defn)
        self.accept()

    @staticmethod
    def _field_style() -> str:
        return ("background-color: #444444; color: #ffffff; "
                "border: 1px solid #777777; border-radius: 4px; padding: 2px 6px;")

    @staticmethod
    def _btn_style(color: str) -> str:
        return (f"QPushButton {{ background-color: {color}; color: #ffffff; "
                "border: none; border-radius: 4px; padding: 0 8px; font-size: 12px; }"
                "QPushButton:hover { background-color: #888888; }")


# ---------------------------------------------------------------------------
# Dialog -- Remplacement visuel d'un CellType existant
# ---------------------------------------------------------------------------

class OverrideIconDialog(QDialog):
    """Dialog pour remplacer visuellement l'icone d'un CellType natif."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Remplacer une icone existante")
        self.setMinimumSize(420, 300)
        self.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")
        self._png_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Remplacer l'icone d'un type existant")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffcc88;")
        layout.addWidget(title)

        hint = QLabel("Le type JSON reste inchangé. Seul l'affichage dans l'éditeur change.")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Sélecteur de type
        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("Type à remplacer :"))
        self._type_combo = QComboBox()
        self._type_combo.setStyleSheet(
            "background:#555; color:#fff; border:1px solid #777; "
            "border-radius:4px; padding:2px 6px;"
        )
        for ct in CellType:
            if ct == CellType.EMPTY:
                continue
            self._type_combo.addItem(
                f"{ct.value}  ({CELL_LABELS.get(ct, ct.value)})",
                userData=ct.value,
            )
        row_type.addWidget(self._type_combo)
        layout.addLayout(row_type)

        # Icone Unicode
        row_uni = QHBoxLayout()
        row_uni.addWidget(QLabel("Nouvelle icone Unicode :"))
        self._unicode_edit = QLineEdit()
        self._unicode_edit.setPlaceholderText("ex: ⚔  (laisser vide pour garder)")
        self._unicode_edit.setMaxLength(4)
        self._unicode_edit.setFixedWidth(80)
        self._unicode_edit.setStyleSheet(
            "background:#444; color:#fff; border:1px solid #777; "
            "border-radius:4px; padding:2px 6px;"
        )
        row_uni.addWidget(self._unicode_edit)
        row_uni.addStretch()
        layout.addLayout(row_uni)

        # PNG
        row_png = QHBoxLayout()
        self._png_label = QLabel("Aucun PNG sélectionné")
        self._png_label.setStyleSheet("color: #888888; font-size: 11px;")
        row_png.addWidget(self._png_label)
        btn_png = QPushButton("Choisir PNG...")
        btn_png.setFixedHeight(28)
        btn_png.setStyleSheet(
            "QPushButton { background-color: #445566; color: #fff; "
            "border: none; border-radius: 4px; padding: 0 8px; }"
            "QPushButton:hover { background-color: #888; }"
        )
        btn_png.clicked.connect(self._on_pick_png)
        row_png.addWidget(btn_png)
        layout.addLayout(row_png)

        layout.addStretch()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("color: #ffffff;")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_pick_png(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image PNG", "", "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self._png_path = path
            self._png_label.setText(Path(path).name)
            self._png_label.setStyleSheet("color: #88cc88; font-size: 11px;")

    def _on_accept(self) -> None:
        type_value = self._type_combo.currentData()
        icon_unicode = self._unicode_edit.text().strip()
        if not icon_unicode and not self._png_path:
            QMessageBox.warning(self, "Rien à remplacer",
                "Saisissez une icone Unicode ou choisissez un PNG.")
            return

        icon_path = None
        if self._png_path:
            try:
                icon_path = import_png(self._png_path)
            except OSError as e:
                QMessageBox.warning(self, "Erreur PNG", f"Impossible de copier le PNG :\n{e}")
                return

        defn = CustomCellDef(
            type_id=type_value,
            label=CELL_LABELS.get(CellType(type_value), type_value),
            color=CELL_COLORS.get(CellType(type_value), (100, 100, 120)),
            icon_unicode=icon_unicode or "?",
            icon_path=icon_path,
        )
        CUSTOM_REGISTRY.set_override(type_value, defn)
        self.accept()


# ---------------------------------------------------------------------------
# Dialog -- Gestion des icones custom (liste + suppression)
# ---------------------------------------------------------------------------

class ManageIconsDialog(QDialog):
    """Dialog listant tous les custom types et overrides, avec suppression."""

    icons_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gérer les icones personnalisées")
        self.setMinimumSize(480, 400)
        self.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #555; }
            QTabBar::tab { background: #3a3a3a; color: #ccc;
                           padding: 4px 12px; border: 1px solid #555; }
            QTabBar::tab:selected { background: #4a6fa5; color: #fff; }
        """)

        # Onglet types custom
        tab_custom = QWidget()
        lay_c = QVBoxLayout(tab_custom)
        self._list_custom = QListWidget()
        self._list_custom.setStyleSheet(
            "background:#1e1e1e; color:#cccccc; border:1px solid #555;"
        )
        self._refresh_custom_list()
        lay_c.addWidget(self._list_custom)
        btn_del_custom = QPushButton("Supprimer le type sélectionné")
        btn_del_custom.setStyleSheet(
            "QPushButton { background:#7a4a4a; color:#fff; border:none; "
            "border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background:#888; }"
        )
        btn_del_custom.clicked.connect(self._on_delete_custom)
        lay_c.addWidget(btn_del_custom)
        tabs.addTab(tab_custom, "Nouveaux types")

        # Onglet overrides
        tab_over = QWidget()
        lay_o = QVBoxLayout(tab_over)
        self._list_over = QListWidget()
        self._list_over.setStyleSheet(
            "background:#1e1e1e; color:#cccccc; border:1px solid #555;"
        )
        self._refresh_override_list()
        lay_o.addWidget(self._list_over)
        btn_del_over = QPushButton("Supprimer le remplacement sélectionné")
        btn_del_over.setStyleSheet(
            "QPushButton { background:#7a4a4a; color:#fff; border:none; "
            "border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background:#888; }"
        )
        btn_del_over.clicked.connect(self._on_delete_override)
        lay_o.addWidget(btn_del_over)
        tabs.addTab(tab_over, "Remplacements visuels")

        layout.addWidget(tabs)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(30)
        btn_close.setStyleSheet(
            "QPushButton { background:#555; color:#fff; border:none; "
            "border-radius:4px; padding:0 12px; }"
        )
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _refresh_custom_list(self) -> None:
        self._list_custom.clear()
        for defn in CUSTOM_REGISTRY.all_custom():
            item = QListWidgetItem(
                f"{defn.icon_unicode}  {defn.label}  [{defn.type_id}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, defn.type_id)
            self._list_custom.addItem(item)

    def _refresh_override_list(self) -> None:
        self._list_over.clear()
        for key, defn in CUSTOM_REGISTRY.all_overrides().items():
            item = QListWidgetItem(
                f"{key} -> {defn.icon_unicode}"
                + (f"  +PNG" if defn.icon_path else "")
            )
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._list_over.addItem(item)

    def _on_delete_custom(self) -> None:
        item = self._list_custom.currentItem()
        if not item:
            return
        type_id = item.data(Qt.ItemDataRole.UserRole)
        CUSTOM_REGISTRY.unregister(type_id)
        self._refresh_custom_list()
        self.icons_changed.emit()

    def _on_delete_override(self) -> None:
        item = self._list_over.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        CUSTOM_REGISTRY.clear_override(key)
        self._refresh_override_list()
        self.icons_changed.emit()
