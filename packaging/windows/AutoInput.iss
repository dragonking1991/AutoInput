; Inno Setup script — compiled by packaging/build.py on Windows (ISCC /DAppVersion=x.y.z).
; Per-user install by default (no admin prompt); the user may choose "all users" instead.
#define AppName "AutoInput"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8C3B5B2E-7F7A-4E55-9C0E-6E9C2B1A4D21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=AutoInput
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename={#AppName}-{#AppVersion}-windows-setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\{#AppName}.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
