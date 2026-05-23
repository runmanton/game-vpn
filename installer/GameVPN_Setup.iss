; ============================================================
; GameVPN Installer - Inno Setup Script
; Bundles GameVPN + WireGuard into one Setup.exe
; ============================================================
; Requirements:
;   1. Build GameVPN.exe first (run BUILD.bat)
;   2. Download WireGuard MSI to installer\ folder
;   3. Compile with Inno Setup Compiler (iscc.exe)
; ============================================================

#define MyAppName "GameVPN"
#define MyAppVersion "1.1.3"
#define MyAppPublisher "Luong Manh Tuan"
#define MyAppURL "https://github.com/runmanton/game-vpn"
#define MyAppExeName "GameVPN.exe"

[Setup]
AppId={{B8A3D5E1-4F2C-4A7B-9D8E-1F3C5A7B9D2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=GameVPN_Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=license.txt
WizardImageFile=wizard_image.bmp
WizardSmallImageFile=wizard_small.bmp
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableWelcomePage=no
SetupLogging=yes
; Smooth upgrade-in-place: auto-close running GameVPN, reuse previous install dir,
; and skip prompts that would otherwise ask the user to confirm the overwrite.
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
UsePreviousLanguage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "installwireguard"; Description: "Install WireGuard (required for VPN tunnel)"; GroupDescription: "Components:"

[Files]
; GameVPN application
Source: "..\dist\GameVPN.exe"; DestDir: "{app}"; Flags: ignoreversion

; WireGuard MSI installer (bundled)
Source: "wireguard-amd64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall; Tasks: installwireguard

; Manual PDF
Source: "..\GameVPN_Manual.pdf"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\User Manual"; Filename: "{app}\GameVPN_Manual.pdf"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install WireGuard silently
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\wireguard-amd64.msi"" /qn /norestart"; StatusMsg: "Installing WireGuard..."; Flags: runhidden waituntilterminated; Tasks: installwireguard

; Launch GameVPN after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch GameVPN"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Note: WireGuard is NOT uninstalled (user may use it for other purposes)

[Code]
// Check if WireGuard is already installed
function IsWireGuardInstalled: Boolean;
var
  Path1, Path2: String;
begin
  Path1 := ExpandConstant('{pf}\WireGuard\wireguard.exe');
  Path2 := ExpandConstant('{pf64}\WireGuard\wireguard.exe');
  Result := FileExists(Path1) or FileExists(Path2);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // If WireGuard already installed, uncheck the install task
  if CurPageID = wpSelectTasks then
  begin
    if IsWireGuardInstalled then
    begin
      WizardForm.TasksList.Checked[1] := False;
      WizardForm.TasksList.ItemCaption[1] :=
        'Install WireGuard (already installed - skip)';
    end;
  end;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  // Show a message about admin rights
  if not IsAdmin then
  begin
    MsgBox('GameVPN requires administrator privileges to install.' + #13#10 +
           'Please right-click the installer and select "Run as administrator".',
           mbError, MB_OK);
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Force-close any running GameVPN.exe so upgrade-in-place never trips on a
  // locked file. /F is safe here: closing the GUI does not tear down the
  // WireGuard tunnel service, which the new app can re-attach to.
  Exec(ExpandConstant('{cmd}'), '/C taskkill /IM GameVPN.exe /F /T',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
