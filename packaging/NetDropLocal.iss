#define MyAppName "NetDrop Local"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "NetDrop"
#define MyAppExeName "NetDropLocal.exe"

[Setup]
AppId={{3D566E93-6C98-4D0B-B5A4-C0F1E7B55A20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NetDrop Local
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=NetDrop-Local-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Files]
Source: "..\dist\NetDropLocal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""NetDrop Local TCP"" dir=in action=allow program=""{app}\{#MyAppExeName}"" protocol=TCP localport=8000 profile=private"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""NetDrop Local Discovery"" dir=in action=allow program=""{app}\{#MyAppExeName}"" protocol=UDP localport=5353 profile=private"; Flags: runhidden

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""NetDrop Local TCP"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""NetDrop Local Discovery"""; Flags: runhidden
