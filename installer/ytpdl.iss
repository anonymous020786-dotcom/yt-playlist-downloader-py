; Inno Setup script for YouTube Playlist Downloader (Python / PySide6 build).
;
; Build the app first:   pyinstaller ytpdl.spec
; Then compile:           ISCC installer\ytpdl.iss
; Output:                 installer\Output\YouTube-Playlist-Downloader-Setup-<ver>.exe
;
; The one-folder PyInstaller build in dist\ is packaged whole. FFmpeg is not
; bundled; the installer offers to fetch it with winget on the finished page.

#define AppName "YouTube Playlist Downloader"
#define AppVersion "2.0.0"
#define AppPublisher "YTPDL contributors"
#define AppURL "https://github.com/shaked6540/YoutubePlaylistDownloader"
#define AppExeName "YouTube Playlist Downloader.exe"
#define SourceDir "..\dist\YouTube Playlist Downloader"

[Setup]
AppId={{12B585FA-E56C-4938-AFDC-CEAC0749FE16}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=YouTube-Playlist-Downloader-Setup-{#AppVersion}
SetupIconFile=..\ytpdl\resources\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "pt_BR"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "ffmpeg"; Description: "Install FFmpeg with winget (needed for video downloads & conversion)"; GroupDescription: "Dependencies:"; Check: WingetAvailable

[Files]
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\READ ME FIRST.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "winget"; Parameters: "install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements"; \
  StatusMsg: "Installing FFmpeg (winget)..."; Flags: runhidden runasoriginaluser skipifsilent; Tasks: ffmpeg
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function WingetAvailable(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('winget', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;
