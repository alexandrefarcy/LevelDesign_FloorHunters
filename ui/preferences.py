"""
ui/preferences.py
Gestion des préférences utilisateur -- raccourcis clavier.

PreferencesManager : charge/sauvegarde ~/.tower_dungeon/prefs.json
PreferencesDialog  : fenêtre de configuration des raccourcis
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox,
    QMessageBox, QAbstractItemView, QKeySequenceEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QKeyCombination
from PyQt6.QtGui import QKeySequence

from ui.constants import DEFAULT_SHORTCUTS, SHORTCUT_LABELS
from core.grid import CUSTOM_REGISTRY


PREFS_PATH = Path.home() / ".tower_dungeon" / "prefs.json"


# ---------------------------------------------------------------------------
# PreferencesManager
# ---------------------------------------------------------------------------

class PreferencesManager:
    """Charge, sauvegarde et expose les raccourcis clavier configurés.

    Usage :
        mgr = PreferencesManager()
        key_str = mgr.get("eraser")   # -> "E"
        mgr.set("eraser", "R")
        mgr.save()
    """

    def __init__(self) -> None:
        self._shortcuts: dict[str, str] = dict(DEFAULT_SHORTCUTS)
        self._load()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get(self, action: str) -> str:
        """Retourne le raccourci configuré pour une action."""
        return self._shortcuts.get(action, DEFAULT_SHORTCUTS.get(action, ""))

    def set(self, action: str, key_sequence: str) -> None:
        """Définit un raccourci pour une action."""
        if action in DEFAULT_SHORTCUTS:
            self._shortcuts[action] = key_sequence

    def get_all(self) -> dict[str, str]:
        """Retourne une copie de tous les raccourcis."""
        return dict(self._shortcuts)

    def reset_to_defaults(self) -> None:
        """Remet tous les raccourcis aux valeurs par défaut."""
        self._shortcuts = dict(DEFAULT_SHORTCUTS)

    def save(self) -> None:
        """Sauvegarde les préférences dans ~/.tower_dungeon/prefs.json."""
        try:
            PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "shortcuts":    self._shortcuts,
                "custom_icons": CUSTOM_REGISTRY.to_dict(),
            }
            with open(PREFS_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass  # Echec silencieux -- ne pas bloquer l'appli

    def save_custom_icons(self) -> None:
        """Sauvegarde uniquement la partie custom_icons (après ajout/suppression)."""
        self.save()

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Charge les préférences depuis le disque si elles existent."""
        if not PREFS_PATH.exists():
            return
        try:
            with open(PREFS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            saved = data.get("shortcuts", {})
            for action in DEFAULT_SHORTCUTS:
                if action in saved and isinstance(saved[action], str):
                    self._shortcuts[action] = saved[action]
            # Restaurer le registre custom
            if "custom_icons" in data:
                CUSTOM_REGISTRY.from_dict(data["custom_icons"])
        except (OSError, json.JSONDecodeError):
            pass  # Fichier corrompu -- on repart des defaults


# ---------------------------------------------------------------------------
# PreferencesDialog
# ---------------------------------------------------------------------------

class PreferencesDialog(QDialog):
    """Fenêtre de configuration des raccourcis clavier.

    Signal :
        shortcuts_changed() : émis à l'acceptation si au moins un raccourci a changé
    """

    shortcuts_changed = pyqtSignal()

    def __init__(self, prefs: PreferencesManager, parent=None) -> None:
        super().__init__(parent)
        self.prefs = prefs
        self._original = prefs.get_all()
        self._pending: dict[str, str] = prefs.get_all()

        self.setWindowTitle("Préférences -- Raccourcis clavier")
        self.setMinimumSize(520, 480)
        self.setStyleSheet("background-color: #2b2b2b; color: #eeeeee;")
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Raccourcis clavier")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #aaccff;"
        )
        layout.addWidget(title)

        hint = QLabel(
            "Cliquez sur une cellule de la colonne Raccourci et appuyez sur la touche souhaitée."
        )
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Tableau action / raccourci
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Action", "Raccourci"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(1, 160)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #555555;
                gridline-color: #3a3a3a;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #3a4a6a;
            }
            QHeaderView::section {
                background-color: #333333;
                color: #aaaaaa;
                padding: 4px;
                border: none;
                font-size: 11px;
            }
        """)
        self._populate_table()
        layout.addWidget(self._table)

        # Zone de saisie de touche
        key_row = QHBoxLayout()
        lbl_key = QLabel("Nouvelle touche :")
        lbl_key.setStyleSheet("color: #cccccc; font-size: 12px;")
        key_row.addWidget(lbl_key)

        self._key_edit = QKeySequenceEdit()
        self._key_edit.setStyleSheet("""
            QKeySequenceEdit {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
            }
        """)
        self._key_edit.setFixedWidth(160)
        key_row.addWidget(self._key_edit)

        btn_apply_key = QPushButton("Appliquer")
        btn_apply_key.setFixedHeight(28)
        btn_apply_key.setStyleSheet(self._btn_style("#4a6fa5"))
        btn_apply_key.clicked.connect(self._on_apply_key)
        key_row.addWidget(btn_apply_key)

        key_row.addStretch()
        layout.addLayout(key_row)

        # Boutons bas
        btn_row = QHBoxLayout()

        btn_reset = QPushButton("Réinitialiser tout")
        btn_reset.setFixedHeight(30)
        btn_reset.setStyleSheet(self._btn_style("#7a4a4a"))
        btn_reset.clicked.connect(self._on_reset_all)
        btn_row.addWidget(btn_reset)

        btn_row.addStretch()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("color: #ffffff;")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        btn_row.addWidget(btns)

        layout.addLayout(btn_row)

    def _populate_table(self) -> None:
        """Remplit le tableau depuis _pending."""
        self._table.setRowCount(0)
        for action, label in SHORTCUT_LABELS.items():
            row = self._table.rowCount()
            self._table.insertRow(row)

            item_label = QTableWidgetItem(label)
            item_label.setData(Qt.ItemDataRole.UserRole, action)
            item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, item_label)

            item_key = QTableWidgetItem(self._pending.get(action, ""))
            item_key.setFlags(item_key.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_key.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, item_key)

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #888888; }}
        """

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_apply_key(self) -> None:
        """Applique la touche saisie à la ligne sélectionnée."""
        selected = self._table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "Aucune sélection",
                "Sélectionnez d'abord une action dans le tableau.",
            )
            return

        key_seq = self._key_edit.keySequence()
        if key_seq.isEmpty():
            QMessageBox.warning(
                self, "Touche vide",
                "Appuyez sur une touche avant de cliquer Appliquer.",
            )
            return

        key_str = key_seq.toString()

        # Vérifier les conflits
        row_idx = self._table.currentRow()
        action = self._table.item(row_idx, 0).data(Qt.ItemDataRole.UserRole)
        for other_action, other_key in self._pending.items():
            if other_action != action and other_key == key_str:
                other_label = SHORTCUT_LABELS.get(other_action, other_action)
                reply = QMessageBox.question(
                    self,
                    "Conflit de raccourci",
                    f"La touche «{key_str}» est déjà assignée à «{other_label}».\n"
                    "Continuer quand même ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        self._pending[action] = key_str
        self._table.item(row_idx, 1).setText(key_str)
        self._key_edit.clear()

    def _on_reset_all(self) -> None:
        reply = QMessageBox.question(
            self,
            "Réinitialiser",
            "Remettre tous les raccourcis aux valeurs par défaut ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._pending = dict(DEFAULT_SHORTCUTS)
        self._populate_table()

    def _on_accept(self) -> None:
        changed = self._pending != self._original
        for action, key in self._pending.items():
            self.prefs.set(action, key)
        self.prefs.save()
        if changed:
            self.shortcuts_changed.emit()
        self.accept()