@echo off
rem ============================================================
rem  cs16db Demo Toolkit - build the AMX Mod X plugin
rem
rem  Needs: cs16setup\tools\amxxpc.exe + amxxpc32.dll
rem         (built once from AMX Mod X sources; already in repo)
rem
rem  Usage:
rem    build_plugin.bat            build demo_toolkit.amxx
rem    build_plugin.bat install    build + install into both CS 1.6 builds
rem ============================================================
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set PC=%ROOT%\tools\amxxpc.exe
set SRC=%ROOT%\plugin\demo_toolkit.sma
set OUT=%ROOT%\plugin\demo_toolkit.amxx
set GAME1=D:\Counter-Strike Build 4554
set GAME2=D:\CS 1.6 GoldClient

if not exist "%PC%" (echo [error] %PC% missing & exit /b 1)
if not exist "%ROOT%\tools\amxxpc32.dll" (echo [error] tools\amxxpc32.dll missing & exit /b 1)

rem include dir: from the installed game if present, else staging
set INC=%GAME1%\cstrike\addons\amxmodx\scripting\include
if not exist "%INC%\amxmodx.inc" set INC=%ROOT%\staging\ab\addons\amxmodx\scripting\include
if not exist "%INC%\amxmodx.inc" (echo [error] amxmodx.inc not found & exit /b 1)

echo Building %SRC% ...
"%PC%" "%SRC%" "-i%INC%" "-o%ROOT%\plugin\demo_toolkit" || (echo [error] compile failed & exit /b 1)
if not exist "%OUT%" (echo [error] no output .amxx & exit /b 1)
echo [ok] %OUT%

if /i not "%~1"=="install" goto :done

for %%G in ("%GAME1%" "%GAME2%") do call :install "%%~G"
goto :done

:install
set "G=%~1"
if not exist "%G%\cstrike" (echo [skip] %G% & goto :eof)
set "P=%G%\cstrike\addons\amxmodx"
if not exist "%P%\plugins" (echo [skip] %G% - no amxmodx & goto :eof)
copy /y "%OUT%" "%P%\plugins\demo_toolkit.amxx" >nul || goto :eof
findstr /C:"demo_toolkit.amxx" "%P%\configs\plugins.ini" >nul 2>&1 || echo demo_toolkit.amxx>> "%P%\configs\plugins.ini"
echo [ok] installed into %G%
goto :eof

:done
echo.
echo Test in game console:  amxx plugins   (demo_toolkit should be listed)
echo Chat/console commands: /rec /stop /status /spot /gospot ^| amx_record amx_stop amx_dtk
endlocal
