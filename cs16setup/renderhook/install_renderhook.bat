@echo off
rem ============================================================
rem  Install CS_RenderHook into a CS 1.6 install.
rem  Expects the package in cs16setup\staging\renderhook_dist\
rem  (distributed by the author; not on GitHub).
rem  Usage: install_renderhook.bat ["D:\path\to\CS 1.6"]
rem ============================================================
setlocal
set ROOT=%~dp0..
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\Counter-Strike Build 4554\cstrike" set GAME=D:\Counter-Strike Build 4554
    if not exist "%GAME%\cstrike" if exist "D:\CS 1.6 GoldClient\cstrike" set GAME=D:\CS 1.6 GoldClient
)
set DIST=%ROOT%\staging\renderhook_dist
if not exist "%GAME%\hl.exe" if not exist "%GAME%\cstrike" (
    echo [error] game dir not found: %GAME%
    exit /b 1
)
if not exist "%DIST%" (
    echo [error] staging\renderhook_dist not found - download CS_RenderHook and unpack it here.
    exit /b 1
)

echo == backup ==
mkdir "%GAME%\renderhook_backup" 2>nul
for %%F in ("%DIST%\*") do (
    if exist "%GAME%\%%~nxF" copy /y "%GAME%\%%~nxF" "%GAME%\renderhook_backup\%%~nxF" >nul 2>&1
)

echo == copy ==
copy /y "%DIST%\*" "%GAME%\" >nul
echo done: %GAME%  (see cs16setup\renderhook\README.md)
endlocal
