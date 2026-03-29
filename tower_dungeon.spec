# tower_dungeon.spec
# Configuration PyInstaller pour Tower Dungeon Level Editor.
#
# Usage (depuis la racine du projet) :
#     pyinstaller tower_dungeon.spec
#
# Prerequis :
#     pip install pyinstaller
#
# Le build produit le dossier dist/TowerDungeonLevelEditor/
# contenant l'executable et toutes ses dependances.
# Ce dossier est celui a packager avec Inno Setup.
#
# Mode onedir : plus fiable que onefile avec PyQt6 (evite les faux positifs antivirus,
# demarrage plus rapide, pas d'extraction temp au lancement).

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Collecte automatique des sous-modules PyQt6 necessaires
# ---------------------------------------------------------------------------

hidden_imports = [
    # PyQt6 - modules utilises par le projet
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.sip",
    # networkx et ses dependances
    "networkx",
    "networkx.algorithms",
    "networkx.classes",
    "networkx.generators",
    "networkx.drawing",
    # Modules internes du projet
    "core",
    "core.grid",
    "core.algorithms",
    "core.generator",
    "core.populator",
    "serialization",
    "serialization.serializer",
    "serialization.autosave",
    "ui",
    "ui.constants",
    "ui.main_window",
    "ui.editor_view",
    "ui.icon_manager",
    "ui.preferences",
]

# ---------------------------------------------------------------------------
# Fichiers de donnees a embarquer
# ---------------------------------------------------------------------------

datas = []

# Collecte les donnees PyQt6 (plugins Qt : plateformes, styles, etc.)
datas += collect_data_files("PyQt6", includes=["Qt6/plugins/**"])

# ---------------------------------------------------------------------------
# Analyse des sources
# ---------------------------------------------------------------------------

a = Analysis(
    ["app.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclusions pour reduire la taille du build
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "unittest",
        "_pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Archive PYZ (bytecode Python)
# ---------------------------------------------------------------------------

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# Executable
# ---------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TowerDungeonLevelEditor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # compression UPX si disponible (optionnel)
    console=False,      # pas de fenetre console (application GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",   # chemin vers l'icone generee par generate_icon.py
    version="version_info.txt",
)

# ---------------------------------------------------------------------------
# Collecte onedir
# ---------------------------------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TowerDungeonLevelEditor",
)
