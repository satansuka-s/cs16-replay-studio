@echo off
rem Restore CS 1.6 files backed up by install_renderhook.bat
setlocal
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\Counter-Strike Build 4554\cstrike" set GAME=D:\Counter-Strike Build 4554
    if not exist "%GAME%\cstrike" if exist "D:\CS 1.6 GoldClient\cstrike" set GAME=D:\CS 1.6 GoldClient
)
if not exist "%GAME%\renderhook_backup" (
    echo [info] no renderhook_backup, nothing to restore
    exit /b 0
)
copy /y "%GAME%\renderhook_backup\*" "%GAME%\" >nul
echo restored %GAME%
endlocal
