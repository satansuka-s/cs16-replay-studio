@echo off
rem ============================================================
rem  Install Trinity Engine into a CS 1.6 install.
rem  Expects the unpacked release in cs16setup\staging\trinity_dist\
rem  (download from trinityengine.ru - not available on GitHub).
rem  Usage: install_trinity.bat ["D:\path\to\CS 1.6"]
rem ============================================================
setlocal
set ROOT=%~dp0..
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\Counter-Strike Build 4554\cstrike" set GAME=D:\Counter-Strike Build 4554
    if not exist "%GAME%\cstrike" if exist "D:\CS 1.6 GoldClient\cstrike" set GAME=D:\CS 1.6 GoldClient
)
set DIST=%ROOT%\staging\trinity_dist
if not exist "%GAME%\hl.exe" if not exist "%GAME%\cstrike" (
    echo [error] game dir not found: %GAME%
    exit /b 1
)

rem --- dist can be an unpacked folder, a .7z or a .zip archive ---
if exist "%DIST%" goto :have_dist
for %%A in ("%ROOT%\staging\trinity.7z" "%ROOT%\staging\trinity.zip" "%ROOT%\staging\trinity_dist.7z" "%ROOT%\staging\trinity_dist.zip") do (
    if exist "%%~A" (
        set ARCH=%%~A
        goto :have_arch
    )
)
echo [error] staging\trinity_dist not found. Download Trinity Engine:
echo   GameBanana (CS 1.6 WIP):  https://gamebanana.com/wips/74956
echo   TWHL (HL 3.10f):          https://twhl.info/vault/view/6664
echo and unpack/put it into %ROOT%\staging\trinity_dist (or as trinity.7z/zip).
exit /b 1

:have_arch
echo [info] extracting %ARCH% ...
set "ARCH=%ARCH%"
mkdir "%DIST%" 2>nul
set SEVENZIP=C:\Program Files\7-Zip\7z.exe
if exist "%SEVENZIP%" (
    "%SEVENZIP%" x -o"%DIST%" -y "%ARCH%" >nul
) else (
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ARCH%' -DestinationPath '%DIST%' -Force" >nul 2>&1
)
if not exist "%DIST%" (echo [error] extraction failed & exit /b 1)

:have_dist

echo == backup ==
mkdir "%GAME%\trinity_backup" 2>nul
for %%F in ("%DIST%\*") do (
    if exist "%GAME%\%%~nxF" copy /y "%GAME%\%%~nxF" "%GAME%\trinity_backup\%%~nxF" >nul 2>&1
)

echo == copy ==
copy /y "%DIST%\*" "%GAME%\" >nul
if exist "%DIST%\trinity_kino.cfg" copy /y "%DIST%\trinity_kino.cfg" "%GAME%\cstrike\cfg\trinity_kino.cfg" >nul

echo == autoexec hook ==
set CFG=%GAME%\cstrike\cfg
if not exist "%CFG%\autoexec.cfg" type nul > "%CFG%\autoexec.cfg"
findstr /C:"exec trinity_kino.cfg" "%CFG%\autoexec.cfg" >nul 2>&1 || echo exec trinity_kino.cfg>> "%CFG%\autoexec.cfg"

echo done: %GAME%  (package files copied; see cs16setup\trinity\README.md)
endlocal
