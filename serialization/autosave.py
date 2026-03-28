"""
serialization/autosave.py
Sauvegarde automatique periodique du projet Tower Dungeon.

- Interval : 30 secondes (configurable)
- Destination : ~/.tower_dungeon/autosave.tdp.json
- Ne touche jamais au fichier principal du projet
- Emet un signal Qt quand la sauvegarde est effectuee ou echoue
- Silencieux si le modele est vide (aucun etage)

Usage :
    autosave = AutoSave(model, serializer)
    autosave.saved.connect(lambda path: status_bar.showMessage(f"Autosave : {path}"))
    autosave.failed.connect(lambda err: status_bar.showMessage(f"Autosave echoue : {err}"))
    autosave.start()
    # ...
    autosave.stop()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.grid import GridModel
from serialization.serializer import Serializer, SerializerError


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

AUTOSAVE_DIR = Path.home() / ".tower_dungeon"
AUTOSAVE_FILE = AUTOSAVE_DIR / "autosave.tdp.json"
AUTOSAVE_INTERVAL_MS = 30_000   # 30 secondes


# ---------------------------------------------------------------------------
# AutoSave
# ---------------------------------------------------------------------------

class AutoSave(QObject):
    """Gestionnaire de sauvegarde automatique periodique.

    Utilise un QTimer pour declencher une sauvegarde toutes les N secondes.
    La sauvegarde est effectuee dans un fichier dedie -- jamais dans le
    fichier principal du projet.

    Signals:
        saved(path: str)  : emis apres une sauvegarde reussie.
        failed(error: str): emis si la sauvegarde echoue.

    Args:
        model:      Le GridModel a sauvegarder (reference, pas copie).
        serializer: Instance du Serializer a utiliser.
        interval_ms: Intervalle en millisecondes (defaut : 30 000).
        path:       Chemin de destination (defaut : ~/.tower_dungeon/autosave.tdp.json).
    """

    saved  = pyqtSignal(str)   # chemin absolu du fichier autosave
    failed = pyqtSignal(str)   # message d'erreur

    def __init__(
        self,
        model:       GridModel,
        serializer:  Serializer,
        interval_ms: int = AUTOSAVE_INTERVAL_MS,
        path:        Optional[Path] = None,
    ) -> None:
        super().__init__()
        self._model      = model
        self._serializer = serializer
        self._path       = path or AUTOSAVE_FILE
        self._timer      = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Controle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Demarre le timer d'autosave."""
        self._timer.start()

    def stop(self) -> None:
        """Arrete le timer d'autosave."""
        self._timer.stop()

    def set_model(self, model: GridModel) -> None:
        """Met a jour la reference au modele (utile apres chargement d'un projet)."""
        self._model = model

    def trigger(self) -> None:
        """Declenche une sauvegarde immediate (sans attendre le prochain tick)."""
        self._on_tick()

    @property
    def path(self) -> Path:
        """Chemin du fichier autosave."""
        return self._path

    @property
    def is_active(self) -> bool:
        """Retourne True si le timer est en cours."""
        return self._timer.isActive()

    # ------------------------------------------------------------------
    # Logique interne
    # ------------------------------------------------------------------

    def _on_tick(self) -> None:
        """Declenche par le QTimer toutes les N secondes."""
        if self._model.floor_count == 0:
            # Rien a sauvegarder
            return

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._serializer.save_project(self._model, self._path)
            self.saved.emit(str(self._path))
        except SerializerError as exc:
            self.failed.emit(str(exc))
        except OSError as exc:
            self.failed.emit(f"Erreur systeme autosave : {exc}")
