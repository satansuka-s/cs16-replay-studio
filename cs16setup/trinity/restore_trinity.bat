@echo off
setlocal EnableExtensions
rem ============================================================
rem  Undo install_trinity.bat
rem
rem  Usage: restore_trinity.bat ["D:\path\to\CS 1.6"] [--keep-metahook]
rem
rem  Removes the Trinity plugin and, unless --keep-metahook is given,
rem  uninstalls MetaHookSv itself. Patched gamedata snapshots are restored
rem  from the *.json.bak files that patch_gamedata_crc.py keeps.
rem ============================================================

set "ROOT=%~dp0.."
set "STAGE=%ROOT%\staging\trinity"
set "GAME="
set "KEEP=0"

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--keep-metahook" (set "KEEP=1" & shift & goto parse)
if /i "%~1"=="--help" goto usage
if /i "%~1"=="-h" goto usage
set "GAME=%~1"
shift
goto parse

:usage
echo Usage: restore_trinity.bat ["D:\path\to\CS 1.6"] [--keep-metahook]
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
    exit /b 1
)
if not exist "%GAME%\cstrike" (
    echo [error] %GAME% does not look like a CS 1.6 install
    exit /b 1
)
echo [info] game: %GAME%

rem ---------- Trinity plugin ----------
set "PLUGINS=%GAME%\cstrike\metahook\plugins"
if exist "%PLUGINS%\TrinityRender.dll" (
    if exist "%PLUGINS%\TrinityRender.dll.bak" (
        copy /y "%PLUGINS%\TrinityRender.dll.bak" "%PLUGINS%\TrinityRender.dll" >nul
        del /q "%PLUGINS%\TrinityRender.dll.bak" >nul 2>&1
        echo [ok] previous TrinityRender.dll restored
    ) else (
        del /q "%PLUGINS%\TrinityRender.dll" >nul 2>&1
        echo [ok] TrinityRender.dll removed
    )
)

set "LST=%GAME%\cstrike\metahook\configs\plugins.lst"
if exist "%LST%" (
    if exist "%LST%.bak" (
        copy /y "%LST%.bak" "%LST%" >nul
        del /q "%LST%.bak" >nul 2>&1
        echo [ok] plugins.lst restored
    ) else (
        type nul > "%LST%"
        echo [ok] plugins.lst cleared
    )
)

rem ---------- gamedata ----------
for %%F in ("%GAME%\cstrike\metahook\gamedata\*.json.bak") do (
    copy /y "%%~fF" "%%~dpnF" >nul
    del /q "%%~fF" >nul 2>&1
    echo [ok] gamedata restored: %%~nF
)

rem ---------- MetaHook ----------
if "%KEEP%"=="1" (
    echo [info] MetaHookSv kept ^(--keep-metahook^)
    exit /b 0
)
if exist "%STAGE%\MetahookInstallerCLI.exe" (
    echo == uninstall MetaHookSv ==
    "%STAGE%\MetahookInstallerCLI.exe" -appid 10 -gamedir "%GAME%" -moddir cstrike -uninstall
    if errorlevel 1 echo [warn] MetahookInstallerCLI -uninstall failed, remove files manually
) else (
    echo [info] MetahookInstallerCLI.exe not found in staging - remove MetaHook files manually:
    echo        "%GAME%\MetaHook.exe" "%GAME%\MetaHook_blob.exe" "%GAME%\cstrike\metahook"
)
echo done: %GAME%
exit /b 0
