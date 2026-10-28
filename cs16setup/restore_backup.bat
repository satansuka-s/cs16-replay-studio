@echo off
rem ============================================================
rem  cs16db Demo Toolkit - restore backups
rem  Usage: restore_backup.bat [game_dir ...]
rem  Restores liblist.gam / autoexec.cfg / addons of each install
rem  from the .bak / addons_backup_* files created by the installer.
rem ============================================================
setlocal EnableExtensions
set GAME1=D:\Counter-Strike Build 4554
set GAME2=D:\CS 1.6 GoldClient

set GAMELIST=
if not "%~1"=="" (
    set GAMELIST=%*
) else (
    if exist "%GAME1%\cstrike" set GAMELIST=%GAMELIST% "%GAME1%"
    if exist "%GAME2%\cstrike" set GAMELIST=%GAMELIST% "%GAME2%"
)

for %%G in (%GAMELIST%) do call :restore "%%~G"
goto :done

:restore
set GAME=%~1
set CR=%GAME%\cstrike
echo === restore %GAME% ===
if exist "%CR%\liblist.gam.bak" (
    copy /y "%CR%\liblist.gam.bak" "%CR%\liblist.gam" >nul
    echo   liblist.gam restored
)
if exist "%CR%\autoexec.cfg.bak" (
    copy /y "%CR%\autoexec.cfg.bak" "%CR%\autoexec.cfg" >nul
    echo   autoexec.cfg restored
)
for /d %%B in ("%CR%\addons_backup_*") do (
    if exist "%CR%\addons" (echo   [keep] addons folder kept; backups: %%~nxB)
)
if exist "%CR%\addons_backup_" (echo   check addons_backup_* for previous addons)
goto :eof

:done
echo.
echo Backups kept for manual review: *_backup_* folders, *.bak files.
endlocal
