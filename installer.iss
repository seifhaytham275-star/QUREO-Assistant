#define MyAppName "QUREO Assistant"
#define MyAppVersion "1.0.0"
#define MyAppExeName "QUREO-Assistant.exe"

[Setup]
AppId={{B8D1B23A-8F7C-4B6D-9C2A-51E4D6A0C713}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\QUREO Assistant
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=QUREO-Assistant-Setup
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\QUREO-Assistant.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\QUREO Assistant"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\QUREO Assistant"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch QUREO Assistant"; Flags: postinstall nowait skipifsilent
