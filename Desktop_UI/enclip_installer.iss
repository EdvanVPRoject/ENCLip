#define MyAppName "ENCLip Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ENCLip"
#define MyAppExeName "ENCLip.exe"
#define SourceDir "D:\ProjekAntigravity\ENCLip\portable"

[Setup]
AppId={{C789A532-6A1B-4E38-B549-9B3B52DF0249}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=D:\ProjekAntigravity\ENCLip\naviteversion
OutputBaseFilename=ENCLip_Setup_v1.0
SetupIconFile=D:\ProjekAntigravity\ENCLip\Desktop_UI\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\icon.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\.env.example"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
