; WSL Deck 安装包脚本（Inno Setup 6）
; 默认为当前用户安装，安装 App 不需要管理员权限。

#define MyAppName "WSL Deck"
#define MyAppVersion "1.0.1"
#define MyAppExeName "WSL Deck.exe"

[Setup]
AppId={{4447AF87-5FA8-4D91-83FA-D49E33306590}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=WSL Deck
SetupIconFile=..\assets\wsl-deck-icon.ico
DefaultDirName={localappdata}\Programs\WSL Deck
DefaultGroupName=WSL Deck
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist
OutputBaseFilename=WSL-Deck-Setup-{#MyAppVersion}
VersionInfoVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "..\dist\WSL Deck\*"; DestDir: "{app}"; Excludes: "config.json,logs\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\WSL Deck\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
