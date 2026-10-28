@echo off
rem Restore CS 1.6 files backed up by install_trinity.bat
setlocal
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\Counter-Strike Build 4554\cstrike" set GAME=D:\Counter-Strike Build 4554
    if not exist "%GAME%\cstrike" if exist "D:\CS 1.6 GoldClient\cstrike" set GAME=D:\CS 1.6 GoldClient
)
if not exist "%GAME%\trinity_backup" (
    echo [info] no trinity_backup, nothing to restore
    exit /b 0
)
copy /y "%GAME%\trinity_backup\*" "%GAME%\" >nul
set CFG=%GAME%\cstrike\cfg
if exist "%CFG%\autoexec.cfg" (
    findstr /V /C:"exec trinity_kino.cfg" "%CFG%\autoexec.cfg" > "%CFG%\autoexec.cfg.tmp" 2>nul
    move /y "%CFG%\autoexec.cfg.tmp" "%CFG%\autoexec.cfg" >nul 2>&1
)
echo restored %GAME%
endlocal
