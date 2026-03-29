; installer.iss
; Script Inno Setup pour Tower Dungeon Level Editor
;
; Prerequis :
;   - Inno Setup 6+ installe (https://jrsoftware.org/isinfo.php)
;   - Le build PyInstaller doit etre termine :
;       pyinstaller tower_dungeon.spec
;   - Le dossier dist\TowerDungeonLevelEditor\ doit exister
;
; Usage :
;   Ouvrir ce fichier dans Inno Setup Compiler, puis Build > Compile
;   OU en ligne de commande :
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; Produit : Output\TowerDungeonLevelEditor_Setup_v1.0.0.exe

; ---------------------------------------------------------------------------
; Metadonnees de l'application
; ---------------------------------------------------------------------------

#define AppName      "Tower Dungeon Level Editor"
#define AppVersion   "1.0.0"
#define AppPublisher "TowerDungeon"
#define AppExeName   "TowerDungeonLevelEditor.exe"
#define AppId        "{{A3F8C2D1-5B4E-4F2A-9C1D-7E8F3A2B6D0C}"
; Note : regenere un AppId unique avec Tools > Generate GUID dans Inno Setup

; ---------------------------------------------------------------------------
; Configuration generale
; ---------------------------------------------------------------------------

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=

; Dossier d'installation par defaut
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

; Pas de droits admin requis (installe dans Program Files par defaut,
; mais l'utilisateur peut choisir son dossier)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Fichier de sortie
OutputDir=Output
OutputBaseFilename=TowerDungeonLevelEditor_Setup_v{#AppVersion}

; Icone de l'installateur
SetupIconFile=assets\icon.ico

; Compression maximale
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Interface
WizardStyle=modern
WizardSmallImageFile=assets\icon.ico

; Infos legales (optionnel - commente si pas de fichier licence)
; LicenseFile=LICENSE.txt

; Architecture cible
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Desinstallateur
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Repertoire des donnees utilisateur (cree au premier lancement par l'appli)
; ~/.tower_dungeon/ est gere par l'application elle-meme via Path.home()

; ---------------------------------------------------------------------------
; Langues
; ---------------------------------------------------------------------------

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

; ---------------------------------------------------------------------------
; Taches (cases a cocher pendant l'installation)
; ---------------------------------------------------------------------------

[Tasks]
Name: "desktopicon";    Description: "Creer un raccourci sur le Bureau";    GroupDescription: "Raccourcis :"; Flags: unchecked
Name: "startmenuicon";  Description: "Creer un raccourci dans le menu Demarrer"; GroupDescription: "Raccourcis :"; Flags: checked

; ---------------------------------------------------------------------------
; Fichiers a installer
; ---------------------------------------------------------------------------

[Files]
; Tout le contenu du build PyInstaller (onedir)
Source: "dist\TowerDungeonLevelEditor\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; ---------------------------------------------------------------------------
; Raccourcis
; ---------------------------------------------------------------------------

[Icons]
; Menu Demarrer
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Tasks: startmenuicon

; Bureau
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon

; Desinstaller (dans le menu Demarrer)
Name: "{group}\Desinstaller {#AppName}"; \
    Filename: "{uninstallexe}"; \
    Tasks: startmenuicon

; ---------------------------------------------------------------------------
; Execution post-installation
; ---------------------------------------------------------------------------

[Run]
; Proposer de lancer l'appli a la fin de l'installation
Filename: "{app}\{#AppExeName}"; \
    Description: "Lancer {#AppName}"; \
    Flags: nowait postinstall skipifsilent

; ---------------------------------------------------------------------------
; Nettoyage a la desinstallation
; ---------------------------------------------------------------------------

[UninstallDelete]
; Supprime les fichiers generes par l'appli dans le dossier d'installation
; (logs, fichiers temporaires eventuels)
Type: filesandordirs; Name: "{app}\__pycache__"

; Note : ~/.tower_dungeon/ (prefs.json, autosave, icones custom)
; n'est PAS supprime a la desinstallation - donnees utilisateur preservees.

; ---------------------------------------------------------------------------
; Messages personnalises
; ---------------------------------------------------------------------------

[CustomMessages]
french.WelcomeLabel2=Cet assistant va installer [name/ver] sur votre ordinateur.%n%nIl est recommande de fermer toutes les autres applications avant de continuer.
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nIt is recommended that you close all other applications before continuing.
