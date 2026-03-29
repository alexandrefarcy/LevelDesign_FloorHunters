"""
app.py
Point d'entree du Tower Dungeon Level Editor.

Lancement :
    python app.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

REQUIRED_PACKAGES = [
    ("PyQt6",    "PyQt6"),
    ("networkx", "networkx"),
]

def check_dependencies() -> None:
    for package_name, import_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            print(f"Erreur : le package {package_name} n'est pas installe.")
            sys.exit(1)


def main() -> None:
    check_dependencies()
    app = QApplication(sys.argv)
    app.setApplicationName("Tower Dungeon Level Editor")
    app.setOrganizationName("TowerDungeon")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()