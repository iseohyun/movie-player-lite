; Movie Player Lite - Inno Setup installer script
; Build with build-installer.bat (it builds the app folder first, then compiles this script).
;
; - Per-user install (no administrator rights): the app writes its settings and logs next to the exe.
; - The wizard asks for the install folder, a desktop shortcut, and which video file types to play by default.
; - FFmpeg is not bundled. During setup the installer looks for FFmpeg (install folder, then PATH);
;   if it is missing or older than FfmpegMinMajor, it offers to download the latest release build.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef FfmpegMinMajor
  ; Recommended minimum FFmpeg major version. Older (or missing) FFmpeg triggers the download offer.
  #define FfmpegMinMajor 7
#endif
#define AppName "Movie Player Lite"
#define AppExe "movie-player-lite.exe"
#define AppSourceDir "dist_installer\movie-player-lite"
#define VideoProgId "MoviePlayerLite.Video"
#define FfmpegZipUrl "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

[Setup]
AppId={{749C7DE7-3939-44E7-93D1-0B35D9C68F0E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
LicenseFile=LICENSE
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=installer_output
OutputBaseFilename=MoviePlayerLite-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ArchiveExtraction=full
CloseApplications=yes
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
english.FfmpegTask=Download the latest FFmpeg (needed for cutting and saving YouTube videos, about 110 MB)
english.AssocGroup=Play these file types with Movie Player Lite by default:
english.VideoTypeName=Movie Player Lite video
english.ExtrasGroup=Additional options:
english.FfmpegDownloadFailed=FFmpeg could not be downloaded. Setup will continue; you can install FFmpeg yourself later.%n%n%1
english.FfmpegInstallFailed=The downloaded FFmpeg could not be installed. Setup will continue; you can install FFmpeg yourself later.%n%n%1
korean.FfmpegTask=최신 FFmpeg 내려받기 (컷팅과 유튜브 저장에 필요, 약 110MB)
korean.AssocGroup=다음 파일 형식을 Movie Player Lite로 기본 재생:
korean.VideoTypeName=Movie Player Lite 동영상
korean.ExtrasGroup=추가 옵션:
korean.FfmpegDownloadFailed=FFmpeg를 내려받지 못했습니다. 설치는 계속되며, FFmpeg는 나중에 직접 설치할 수 있습니다.%n%n%1
korean.FfmpegInstallFailed=내려받은 FFmpeg를 설치하지 못했습니다. 설치는 계속되며, FFmpeg는 나중에 직접 설치할 수 있습니다.%n%n%1
german.FfmpegTask=Neuestes FFmpeg herunterladen (für Schnitt und YouTube-Speicherung erforderlich, ca. 110 MB)
german.AssocGroup=Diese Dateitypen standardmäßig mit Movie Player Lite abspielen:
german.VideoTypeName=Movie Player Lite-Video
german.ExtrasGroup=Zusätzliche Optionen:
german.FfmpegDownloadFailed=FFmpeg konnte nicht heruntergeladen werden. Die Installation wird fortgesetzt; FFmpeg kann später manuell installiert werden.%n%n%1
german.FfmpegInstallFailed=Das heruntergeladene FFmpeg konnte nicht installiert werden. Die Installation wird fortgesetzt; FFmpeg kann später manuell installiert werden.%n%n%1
spanish.FfmpegTask=Descargar la última versión de FFmpeg (necesario para cortar y guardar vídeos de YouTube, unos 110 MB)
spanish.AssocGroup=Reproducir estos tipos de archivo con Movie Player Lite de forma predeterminada:
spanish.VideoTypeName=Vídeo de Movie Player Lite
spanish.ExtrasGroup=Opciones adicionales:
spanish.FfmpegDownloadFailed=No se pudo descargar FFmpeg. La instalación continuará; puedes instalar FFmpeg más tarde por tu cuenta.%n%n%1
spanish.FfmpegInstallFailed=No se pudo instalar el FFmpeg descargado. La instalación continuará; puedes instalar FFmpeg más tarde por tu cuenta.%n%n%1
brazilianportuguese.FfmpegTask=Baixar o FFmpeg mais recente (necessário para cortar e salvar vídeos do YouTube, cerca de 110 MB)
brazilianportuguese.AssocGroup=Reproduzir estes tipos de arquivo com o Movie Player Lite por padrão:
brazilianportuguese.VideoTypeName=Vídeo do Movie Player Lite
brazilianportuguese.ExtrasGroup=Opções adicionais:
brazilianportuguese.FfmpegDownloadFailed=Não foi possível baixar o FFmpeg. A instalação continuará; você pode instalar o FFmpeg depois.%n%n%1
brazilianportuguese.FfmpegInstallFailed=Não foi possível instalar o FFmpeg baixado. A instalação continuará; você pode instalar o FFmpeg depois.%n%n%1

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; One checkbox per file type; none is selected by default so existing default players are left alone
Name: "assoc_mp4"; Description: ".mp4"; GroupDescription: "{cm:AssocGroup}"; Flags: unchecked
Name: "assoc_mkv"; Description: ".mkv"; GroupDescription: "{cm:AssocGroup}"; Flags: unchecked
Name: "assoc_mov"; Description: ".mov"; GroupDescription: "{cm:AssocGroup}"; Flags: unchecked
Name: "assoc_avi"; Description: ".avi"; GroupDescription: "{cm:AssocGroup}"; Flags: unchecked
Name: "assoc_webm"; Description: ".webm"; GroupDescription: "{cm:AssocGroup}"; Flags: unchecked
; Shown only when FFmpeg is missing or older than the recommended version
Name: "ffmpeg"; Description: "{cm:FfmpegTask}"; GroupDescription: "{cm:ExtrasGroup}"; Check: NeedsFfmpeg

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Always: list the app under "Open with" for video files (does not change any default player)
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""
; File type shared by every extension the user ticks on the tasks page
Root: HKCU; Subkey: "Software\Classes\{#VideoProgId}"; ValueType: string; ValueData: "{cm:VideoTypeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#VideoProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\{#VideoProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
; Per ticked extension: make this app the per-user default. If the user already chose another default in
; Windows Settings, Windows keeps that choice and offers this app the next time such a file is opened.
Root: HKCU; Subkey: "Software\Classes\.mp4"; ValueType: string; ValueData: "{#VideoProgId}"; Flags: uninsdeletevalue; Tasks: assoc_mp4
Root: HKCU; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "{#VideoProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_mp4
Root: HKCU; Subkey: "Software\Classes\.mkv"; ValueType: string; ValueData: "{#VideoProgId}"; Flags: uninsdeletevalue; Tasks: assoc_mkv
Root: HKCU; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "{#VideoProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_mkv
Root: HKCU; Subkey: "Software\Classes\.mov"; ValueType: string; ValueData: "{#VideoProgId}"; Flags: uninsdeletevalue; Tasks: assoc_mov
Root: HKCU; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: string; ValueName: "{#VideoProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_mov
Root: HKCU; Subkey: "Software\Classes\.avi"; ValueType: string; ValueData: "{#VideoProgId}"; Flags: uninsdeletevalue; Tasks: assoc_avi
Root: HKCU; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: string; ValueName: "{#VideoProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_avi
Root: HKCU; Subkey: "Software\Classes\.webm"; ValueType: string; ValueData: "{#VideoProgId}"; Flags: uninsdeletevalue; Tasks: assoc_webm
Root: HKCU; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: string; ValueName: "{#VideoProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_webm

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Files the app (or this installer) creates next to the exe: downloaded ffmpeg, logs, hotkey settings.
; History and the YouTube cache live in %APPDATA%\MP4-Trim and are left in place.
Type: filesandordirs; Name: "{app}"

[Code]
const
  FfmpegMinMajor = {#FfmpegMinMajor};
  FfmpegZipUrl = '{#FfmpegZipUrl}';
  FfmpegVersionUnknownButPresent = 9999;

var
  DownloadPage: TDownloadWizardPage;
  SystemFfmpegMajor: Integer;
  SystemFfmpegQueried: Boolean;
  FfmpegDownloaded: Boolean;

{ "ffmpeg version 8.1.2-..." -> 8. Returns -1 when the text is not FFmpeg output.
  Git/nightly builds ("ffmpeg version N-1234-g...") have no number and count as up to date. }
function ParseFfmpegMajor(const Output: String): Integer;
var
  P, I: Integer;
  Tail, Digits: String;
begin
  Result := -1;
  P := Pos('ffmpeg version ', Output);
  if P = 0 then
    Exit;
  Tail := Copy(Output, P + Length('ffmpeg version '), 20);
  Digits := '';
  I := 1;
  while (I <= Length(Tail)) and (Tail[I] >= '0') and (Tail[I] <= '9') do begin
    Digits := Digits + Tail[I];
    I := I + 1;
  end;
  if Digits = '' then
    Result := FfmpegVersionUnknownButPresent
  else
    Result := StrToIntDef(Digits, FfmpegVersionUnknownButPresent);
end;

{ Runs "<Command> -version" and returns the major version, or -1 if it cannot be run. }
function QueryFfmpegMajor(const Command: String): Integer;
var
  OutputFile: String;
  ResultCode: Integer;
  Data: AnsiString;
begin
  Result := -1;
  OutputFile := ExpandConstant('{tmp}\ffmpeg_version.txt');
  DeleteFile(OutputFile);
  if Exec(ExpandConstant('{cmd}'), '/C "' + Command + ' -version > "' + OutputFile + '" 2>&1"', '',
          SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if LoadStringFromFile(OutputFile, Data) then
      Result := ParseFfmpegMajor(String(Data));
end;

{ True when neither the install folder nor PATH has FFmpeg of the recommended version. }
function NeedsFfmpeg: Boolean;
var
  InstalledExe: String;
begin
  InstalledExe := AddBackslash(WizardDirValue) + 'ffmpeg.exe';
  if FileExists(InstalledExe) then begin
    Result := QueryFfmpegMajor('"' + InstalledExe + '"') < FfmpegMinMajor;
    Log(Format('FFmpeg in install folder: needs download = %d', [Integer(Result)]));
    Exit;
  end;
  if not SystemFfmpegQueried then begin
    SystemFfmpegMajor := QueryFfmpegMajor('ffmpeg');
    SystemFfmpegQueried := True;
    Log(Format('FFmpeg on PATH: major version %d (recommended >= %d)', [SystemFfmpegMajor, FfmpegMinMajor]));
  end;
  Result := SystemFfmpegMajor < FfmpegMinMajor;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

{ The publisher posts the SHA-256 of the current release next to the zip; use it to detect a corrupted download. }
function FetchFfmpegZipHash: String;
var
  Data: AnsiString;
begin
  Result := '';
  DownloadTemporaryFile(FfmpegZipUrl + '.sha256', 'ffmpeg.zip.sha256', '', nil);
  if LoadStringFromFile(ExpandConstant('{tmp}\ffmpeg.zip.sha256'), Data) then
    Result := Lowercase(Copy(Trim(String(Data)), 1, 64));
  if Length(Result) <> 64 then
    RaiseException('Unexpected SHA-256 file content');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID <> wpReady) or (not WizardIsTaskSelected('ffmpeg')) then
    Exit;
  FfmpegDownloaded := False;
  DownloadPage.Clear;
  DownloadPage.Show;
  try
    try
      DownloadPage.Add(FfmpegZipUrl, 'ffmpeg.zip', FetchFfmpegZipHash);
      DownloadPage.Download;
      FfmpegDownloaded := True;
    except
      if DownloadPage.AbortedByUser then
        Log('FFmpeg download aborted by user.')
      else
        SuppressibleMsgBox(FmtMessage(CustomMessage('FfmpegDownloadFailed'), [GetExceptionMessage]),
                           mbError, MB_OK, IDOK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;

{ The zip holds one top-level folder (ffmpeg-<version>-essentials_build) with bin\ffmpeg.exe inside. }
function FindExtractedFfmpeg(const ExtractDir: String): String;
var
  FindRec: TFindRec;
  Candidate: String;
begin
  Result := '';
  if FindFirst(AddBackslash(ExtractDir) + '*', FindRec) then begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
          Candidate := AddBackslash(ExtractDir) + FindRec.Name + '\bin\ffmpeg.exe';
          if FileExists(Candidate) then begin
            Result := Candidate;
            Exit;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExtractDir, SourceExe: String;
begin
  if (CurStep <> ssPostInstall) or (not FfmpegDownloaded) then
    Exit;
  try
    ExtractDir := ExpandConstant('{tmp}\ffmpeg_extract');
    ExtractArchive(ExpandConstant('{tmp}\ffmpeg.zip'), ExtractDir, '', True, nil);
    SourceExe := FindExtractedFfmpeg(ExtractDir);
    if SourceExe = '' then
      RaiseException('ffmpeg.exe was not found in the downloaded archive');
    if not CopyFile(SourceExe, ExpandConstant('{app}\ffmpeg.exe'), False) then
      RaiseException('Could not copy ffmpeg.exe to the install folder');
    Log('FFmpeg installed to ' + ExpandConstant('{app}\ffmpeg.exe'));
  except
    SuppressibleMsgBox(FmtMessage(CustomMessage('FfmpegInstallFailed'), [GetExceptionMessage]),
                       mbError, MB_OK, IDOK);
  end;
end;
