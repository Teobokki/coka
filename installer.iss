#define MyVer "1.0.0.1"
[Setup]
AppId={{3B5D1D44-A7D9-4FD3-BCE1-4AF7672D7B55}
AppName=COKA - CALL OF KIMS ARMY
AppVersion={#MyVer}
AppVerName=COKA - CALL OF KIMS ARMY {#MyVer}
AppPublisher=EX Inc./HYPERION DIGITAL
AppPublisherURL=https://github.com/Teobokki/coka
AppCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoVersion=1.0.0.1
VersionInfoCompany=EX Inc./HYPERION DIGITAL
VersionInfoCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoProductName=COKA - CALL OF KIMS ARMY
VersionInfoDescription=COKA Setup
DefaultDirName={localappdata}\Programs\COKA
DefaultGroupName=COKA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=COKA-Setup-{#MyVer}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\COKA.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\COKA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\COKA - CALL OF KIMS ARMY"; Filename: "{app}\COKA.exe"
Name: "{group}\Uninstall COKA"; Filename: "{uninstallexe}"
Name: "{userdesktop}\COKA - CALL OF KIMS ARMY"; Filename: "{app}\COKA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\COKA.exe"; Description: "Launch COKA now"; Flags: nowait postinstall skipifsilent
