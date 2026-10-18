; Neurix Hub Alpha 0.4 - per-user installer
; Compile this file from %USERPROFILE%\NH04 after running build.ps1.
#define MyAppName "Neurix Hub"
#define MyAppVersion "0.4"
#define MyAppExe "NeurixHub-Alpha-0.4.exe"

[Setup]
AppId=NeurixHub
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Neurix Group
DefaultDirName={localappdata}\Programs\Neurix Hub
DefaultGroupName=Neurix Hub
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
Compression=lzma
SolidCompression=yes
OutputDir=release
OutputBaseFilename=NeurixHub-Alpha-0.4-Setup
UninstallDisplayIcon={app}\{#MyAppExe}
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "dist\NeurixHub-Alpha-0.4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Neurix Hub"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\Neurix Hub"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Lancer Neurix Hub"; Flags: nowait postinstall skipifsilent
