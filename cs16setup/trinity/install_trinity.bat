@echo off
setlocal EnableExtensions
rem ============================================================
rem  MetaHookSv + Trinity Engine (renderer) for CS 1.6
rem
rem  Usage:
rem    install_trinity.bat ["D:\path\to\CS 1.6"] [--enable] [--force]
rem
rem    --enable   also switch Trinity on (writes configs\plugins.lst)
rem    --force    continue even if the engine build is unsupported
rem
rem  Steps:
rem    1. download MetaHookSv (launcher + plugins + gamedata) and
rem       TrinityRender.dll from their GitHub releases into staging
rem    2. install MetaHookSv: MetahookInstallerCLI -appid 10 -moddir cstrike
rem    3. drop TrinityRender.dll into cstrike\metahook\plugins
rem    4. patch the engine CRC64 in gamedata (patch_gamedata_crc.py)
rem    5. write configs\plugins.lst (Trinity on with --enable, off otherwise)
rem
rem  Known limits (see README.md):
rem    * MetaHook needs a gamedata snapshot for the exact hw.dll build.
rem      "blob host" repacks (e.g. GoldClient build 10846) have no snapshot
rem      and are refused here instead of crashing the game later.
rem    * Trinity's mp.dll (ReGame for the new engine) is NOT installed:
rem      it breaks 4554 with "Game DLL version mismatch".
rem ============================================================

set "ROOT=%~dp0.."
set "STAGE=%ROOT%\staging\trinity"
set "GAME="
set "ENABLE=0"
set "FORCE=0"

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--enable" (set "ENABLE=1" & shift & goto parse)
if /i "%~1"=="--force"  (set "FORCE=1"  & shift & goto parse)
if /i "%~1"=="--help"   goto usage
if /i "%~1"=="-h"       goto usage
set "GAME=%~1"
shift
goto parse

:usage
echo Usage: install_trinity.bat ["D:\path\to\CS 1.6"] [--enable] [--force]
exit /b 0

:parsed
if not defined GAME (
    if exist "D:\Counter-Strike Build 4554\cstrike" set "GAME=D:\Counter-Strike Build 4554"
)
if not defined GAME (
    if exist "D:\CS 1.6 GoldClient\cstrike" set "GAME=D:\CS 1.6 GoldClient"
)
if not defined GAME (
    echo [error] no game directory given and none auto-detected.
    echo         install_trinity.bat "D:\path\to\CS 1.6"
    exit /b 1
)
if not exist "%GAME%\cstrike\liblist.gam" (
    echo [error] %GAME% does not look like a CS 1.6 install ^(no cstrike\liblist.gam^)
    exit /b 1
)
echo [info] game: %GAME%

rem ---------- python ----------
set "PY="
for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY (
    echo [warn] python.exe not found in PATH - gamedata CRC patch will be skipped
    echo        and MetaHook will not start on a non-retail hw.dll.
)

rem ---------- engine check ----------
if defined PY (
    python "%ROOT%\trinity\patch_gamedata_crc.py" "%GAME%" --dry-run
    if errorlevel 1 (
        if "%FORCE%"=="0" (
            echo.
            echo [error] this engine build is not supported by MetaHook gamedata.
            echo         Nothing was installed. Use build 4554/8684, or pass --force
            echo         to install anyway ^(the game will not start with MetaHook^).
            exit /b 2
        )
        echo [warn] continuing on an unsupported engine because of --force
    )
)

rem ---------- staging ----------
if not exist "%STAGE%" mkdir "%STAGE%" >nul 2>&1
set "ARCH=%STAGE%\MetaHookSv-windows-x86.7z"
set "TRINITY=%STAGE%\TrinityRender.dll"
set "SEVENZR=%STAGE%\7zr.exe"

call :download "https://github.com/MetaHookSv/MetaHookSv/releases/download/v20261027a/MetaHookSv-windows-x86.7z" "%ARCH%" || exit /b 1
call :download "https://github.com/ollerjoaco/Trinity-EngineSv/releases/download/v0.2.0/TrinityRender.dll" "%TRINITY%" || exit /b 1
call :download "https://www.7-zip.org/a/7zr.exe" "%SEVENZR%" || exit /b 1

if not exist "%STAGE%\install\output\MetaHook.exe" (
    echo [info] extracting MetaHookSv ...
    "%SEVENZR%" x -o"%STAGE%" -y "%ARCH%" >nul
    if not exist "%STAGE%\install\output\MetaHook.exe" (
        echo [error] extraction failed: %ARCH%
        exit /b 1
    )
)

rem ---------- install MetaHook ----------
echo == MetaHookSv ==
"%STAGE%\MetahookInstallerCLI.exe" -appid 10 -gamedir "%GAME%" -moddir cstrike -source "%STAGE%\install\output"
if errorlevel 1 (
    echo [error] MetahookInstallerCLI failed
    exit /b 1
)

rem ---------- Trinity plugin ----------
echo == Trinity Engine ==
set "PLUGINS=%GAME%\cstrike\metahook\plugins"
if not exist "%PLUGINS%" mkdir "%PLUGINS%" >nul 2>&1
if exist "%PLUGINS%\TrinityRender.dll" if not exist "%PLUGINS%\TrinityRender.dll.bak" (
    copy /y "%PLUGINS%\TrinityRender.dll" "%PLUGINS%\TrinityRender.dll.bak" >nul
)
copy /y "%TRINITY%" "%PLUGINS%\TrinityRender.dll" >nul
if errorlevel 1 (
    echo [error] could not copy TrinityRender.dll into %PLUGINS%
    exit /b 1
)

rem ---------- gamedata ----------
if defined PY (
    echo == gamedata ==
    python "%ROOT%\trinity\patch_gamedata_crc.py" "%GAME%"
    if errorlevel 1 (
        echo [warn] gamedata patch failed; MetaHook may refuse to start
    )
)

rem ---------- plugin list ----------
set "LST=%GAME%\cstrike\metahook\configs\plugins.lst"
if "%ENABLE%"=="1" (
    echo TrinityRender.dll> "%LST%"
    echo [info] Trinity ENABLED ^(%LST%^)
) else (
    if exist "%LST%" copy /y "%LST%" "%LST%.bak" >nul 2>&1
    type nul > "%LST%"
    echo [info] Trinity installed but DISABLED ^(empty plugins.lst^)
    echo        enable later:  echo TrinityRender.dll^> "%LST%"
)

echo.
echo done: %GAME%
echo   launch: "%GAME%\MetaHook.exe" -game cstrike -steam
echo   revert: cs16setup\trinity\restore_trinity.bat "%GAME%"
exit /b 0

rem ============================================================
:download
rem %1 = url, %2 = output file
if exist "%~2" (
    echo [skip] %~nx2 already downloaded
    exit /b 0
)
echo [get ] %~nx2
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2' } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    if exist "%~2" del /q "%~2" >nul 2>&1
    echo [error] download failed: %~1
    exit /b 1
)
exit /b 0
