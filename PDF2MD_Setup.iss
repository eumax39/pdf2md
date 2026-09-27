[Setup]
AppId={{D37F20B2-1E82-4C10-91B1-02E098F3971C}}
AppName=PDF2MD Converter Pro
AppVersion=2.2.5
AppPublisher=Maxwell Barros Veras de Araujo
AppPublisherURL=https://github.com/eumax39/pdf2md
AppSupportURL=https://github.com/eumax39/pdf2md
AppUpdatesURL=https://github.com/eumax39/pdf2md/releases
DefaultDirName={autopf}\PDF2MD Converter Pro
DefaultGroupName=PDF2MD Converter Pro
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=PDF2MD_Setup
SetupIconFile=icone.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\PDF2MD_V2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PDF2MD Pro"; Filename: "{app}\PDF2MD_V2.exe"
Name: "{autodesktop}\PDF2MD Pro"; Filename: "{app}\PDF2MD_V2.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PDF2MD_V2.exe"; Description: "{cm:LaunchProgram,PDF2MD Pro}"; Flags: nowait postinstall skipifsilent
