"""
app.py
Point d'entrée du Tower Dungeon Level Editor.

Lancement :
    python app.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Tower Dungeon Level Editor")
    app.setOrganizationName("TowerDungeon")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
