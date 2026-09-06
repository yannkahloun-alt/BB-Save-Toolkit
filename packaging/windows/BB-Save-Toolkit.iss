#define MyAppName "BB Save Toolkit"
#define MyAppExeName "BB-Save-Toolkit.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C7EF6FD-2A40-4C84-A91C-A2D60E194A2D}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=yannkahloun-alt
DefaultDirName={localappdata}\Programs\BB-Save-Toolkit
DefaultGroupName=BB Save Toolkit
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.10240
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SourceDir=..\..\
OutputDir=dist\windows
OutputBaseFilename=BB-Save-Toolkit-{#AppVersion}-setup
#ifdef SignedBuild
SignTool=signtool
SignedUninstaller=yes
#endif

[Tasks]
Name: "autostart"; Description: "Start BB Save Toolkit automatically when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "dist\BB-Save-Toolkit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Open BB Save Toolkit"; Filename: "{app}\{#MyAppExeName}"; Parameters: "open"; WorkingDir: "{app}"
Name: "{group}\Restart BB Save Toolkit"; Filename: "{app}\{#MyAppExeName}"; Parameters: "restart"; WorkingDir: "{app}"
Name: "{group}\Stop BB Save Toolkit"; Filename: "{app}\{#MyAppExeName}"; Parameters: "stop"; WorkingDir: "{app}"
Name: "{userstartup}\BB Save Toolkit"; Filename: "{app}\{#MyAppExeName}"; Parameters: "background"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "open"; Description: "Open BB Save Toolkit"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "stop"; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
var
  DeleteUserData: Boolean;

function HasParameter(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
  begin
    if CompareText(ParamStr(I), Name) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  ExistingExe: String;
begin
  Result := '';
  ExistingExe := ExpandConstant('{app}\{#MyAppExeName}');
  if FileExists(ExistingExe) then
  begin
    if not Exec(ExistingExe, 'stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      Result := 'Unable to stop the currently installed BB Save Toolkit process. Close it and retry.';
    end
    else if ResultCode <> 0 then
    begin
      Result := Format(
        'BB Save Toolkit could not stop the running application (exit code %d). Close it and retry.',
        [ResultCode]);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Choice: Integer;
  UserStateRoot: String;
  RuntimeRoot: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    DeleteUserData := HasParameter('/DELETEUSERDATA');
    if (not DeleteUserData) and (not UninstallSilent) then
    begin
      Choice := SuppressibleMsgBox(
        'Keep your BB Save Toolkit settings, selected-save preference, archetypes, and assigned builds for a future reinstall?',
        mbConfirmation, MB_YESNO, IDYES);
      DeleteUserData := Choice = IDNO;
    end;
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    RuntimeRoot := AddBackslash(GetEnv('TEMP')) + 'BB-Save-Toolkit';
    DelTree(RuntimeRoot, True, True, True);
    if DeleteUserData then
    begin
      UserStateRoot := ExpandConstant('{localappdata}\BB-Save-Toolkit');
      DelTree(UserStateRoot, True, True, True);
    end;
  end;
end;
