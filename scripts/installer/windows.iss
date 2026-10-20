; OhMyMeme Windows Installer (Inno Setup)
; 编译: iscc windows.iss

#define MyAppName "MemeCollector"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "MemeCollector contributors / OhMyMeme contributors"
#define MyAppURL "https://github.com/OhMyMeme/OhMyMeme"
#define MyAppExeName "MemeCollector.exe"
#define SourceDir "..\..\dist\src.dist"

[Setup]
AppId={{CD617A0B-7DE6-4F77-BE12-42463483D331}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist
OutputBaseFilename=MemeCollector-{#MyAppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableStartupPrompt=yes
CloseApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "开机自动启动"; GroupDescription: "启动选项"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"" --silent"; Tasks: autostart; Flags: uninsdeletevalue

[InstallDelete]
; 升级时清理旧版启动文件夹快捷方式（v0.2.1 及之前使用文件夹方式）
Name: "{userstartup}\{#MyAppName}.lnk"; Type: files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: ""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: postinstall nowait skipifsilent
