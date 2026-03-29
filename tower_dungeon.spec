# tower_dungeon.spec
# Configuration PyInstaller pour Tower Dungeon Level Editor.
#
# Mode onedir : plus fiable que onefile avec PyQt6.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Imports caches -- collect_submodules garantit l'inclusion complete
# ---------------------------------------------------------------------------

hidden_imports = [
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.sip",
]

# Collecte automatique de TOUS les sous-modules des packages internes
# Evite les ModuleNotFoundError au lancement de l'exe
hidden_imports += collect_submodules("core")
hidden_imports += collect_submodules("serialization")
hidden_imports += collect_submodules("ui")
hidden_imports += collect_submodules("networkx")

# ---------------------------------------------------------------------------
# Fichiers de donnees a embarquer
# ---------------------------------------------------------------------------

datas = []
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
# Archive PYZ
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
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
