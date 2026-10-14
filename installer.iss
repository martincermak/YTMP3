#define MyAppName "YT MP3"
#define MyAppVersion "1.0.0"
#define MyAppExe "YTMP3.exe"

[Setup]
AppId={{B6B0E5B2-3F2A-4C55-9E57-6D1A5B7C9A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Instalace pro aktuálního uživatele: bez admina a složka je zapisovatelná,
; takže si appka může vedle sebe stáhnout/aktualizovat yt-dlp a ffmpeg.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\YTMP3
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=installer
OutputBaseFilename=YTMP3-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExe}

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvořit ikonu na ploše"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
; závislosti stažené skriptem fetch_deps.py (yt-dlp, ffmpeg, ffprobe, deno)
Source: "deps\*.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Spustit YT MP3"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; yt-dlp se může aktualizovat samo, tak při odinstalaci smažeme celou složku
Type: filesandordirs; Name: "{app}"
