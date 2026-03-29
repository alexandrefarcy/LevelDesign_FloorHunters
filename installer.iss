; installer.iss
; Script Inno Setup pour Tower Dungeon Level Editor
;
; Utilise par GitHub Actions -- ne pas compiler manuellement.
; La version est passee en parametre par le workflow :
;   ISCC.exe /DAppVersion=1.0.1 installer.iss

; ---------------------------------------------------------------------------
; Metadonnees
; ---------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppName      "Tower Dungeon Level Editor"
#define AppPublisher "TowerDungeon"
#define AppExeName   "TowerDungeonLevelEditor.exe"
#define AppId        "{{A3F8C2D1-5B4E-4F2A-9C1D-7E8F3A2B6D0C}"

; ---------------------------------------------------------------------------
; Configuration generale
; ---------------------------------------------------------------------------

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}

; Dossier d'installation -- l'utilisateur peut le modifier
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

; Fichier de sortie
OutputDir=Output
OutputBaseFilename=TowerDungeonLevelEditor_Setup_v{#AppVersion}

; Icone de l'installateur
SetupIconFile=assets\icon.ico

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; Interface moderne
WizardStyle=modern

; Architecture 64 bits
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Desinstallateur
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; ---------------------------------------------------------------------------
; Langues
; ---------------------------------------------------------------------------

[Languages]
Name: "french";  MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

; ---------------------------------------------------------------------------
; Taches (cases a cocher pendant l'installation)
; ---------------------------------------------------------------------------

[Tasks]
Name: "desktopicon"; \
    Description: "Creer un raccourci sur le Bureau"; \
    GroupDescription: "Raccourcis :"

; ---------------------------------------------------------------------------
; Fichiers a installer
; ---------------------------------------------------------------------------

[Files]
Source: "dist\TowerDungeonLevelEditor\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; ---------------------------------------------------------------------------
; Raccourcis
; ---------------------------------------------------------------------------

[Icons]
; Raccourci Bureau
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon

; Menu Demarrer
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"

; Desinstaller
Name: "{group}\Desinstaller {#AppName}"; \
    Filename: "{uninstallexe}"

; ---------------------------------------------------------------------------
; Lancement apres installation
; ---------------------------------------------------------------------------

[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "Lancer {#AppName}"; \
    Flags: nowait postinstall skipifsilent

; ---------------------------------------------------------------------------
; Nettoyage desinstallation
; ---------------------------------------------------------------------------

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
