@echo off
rem ============================================================
rem  cs16db Demo Toolkit - build the AMX Mod X plugins
rem
rem  Needs: cs16setup\tools\amxxpc.exe + amxxpc32.dll
rem         (built once from AMX Mod X sources; already in repo)
rem
rem  Plugins:
rem    demo_toolkit.sma          record/names/events/spots (core)
rem    demo_toolkit_daynight.sma cinematic light day/dusk/night
rem
rem  Usage:
rem    build_plugin.bat            build both .amxx
rem    build_plugin.bat install    build + install into both CS 1.6 builds
rem ============================================================
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set PC=%ROOT%\tools\amxxpc.exe
set GAME1=D:\Counter-Strike Build 4554
set GAME2=D:\CS 1.6 GoldClient

if not exist "%PC%" (echo [error] %PC% missing & exit /b 1)
if not exist "%ROOT%\tools\amxxpc32.dll" (echo [error] tools\amxxpc32.dll missing & exit /b 1)

rem include dir: from the installed game if present, else staging
set INC=%GAME1%\cstrike\addons\amxmodx\scripting\include
if not exist "%INC%\amxmodx.inc" set INC=%ROOT%\staging\ab\addons\amxmodx\scripting\include
if not exist "%INC%\amxmodx.inc" (echo [error] amxmodx.inc not found & exit /b 1)

for %%S in (demo_toolkit.sma demo_toolkit_daynight.sma) do (
    echo Building %%S ...
    "%PC%" "%ROOT%\plugin\%%S" "-i%INC%" "-o%ROOT%\plugin\%%~nS" || (echo [error] compile failed: %%S & exit /b 1)
)
echo [ok] built demo_toolkit.amxx + demo_toolkit_daynight.amxx

if /i not "%~1"=="install" goto :done

for %%G in ("%GAME1%" "%GAME2%") do call :install "%%~G"
goto :done

:install
set "G=%~1"
if not exist "%G%\cstrike" (echo [skip] %G% & goto :eof)
set "P=%G%\cstrike\addons\amxmodx"
if not exist "%P%\plugins" (echo [skip] %G% - no amxmodx & goto :eof)
copy /y "%ROOT%\plugin\demo_toolkit.amxx" "%P%\plugins\demo_toolkit.amxx" >nul || goto :eof
copy /y "%ROOT%\plugin\demo_toolkit_daynight.amxx" "%P%\plugins\demo_toolkit_daynight.amxx" >nul || goto :eof
findstr /C:"demo_toolkit.amxx" "%P%\configs\plugins.ini" >nul 2>&1 || echo demo_toolkit.amxx>> "%P%\configs\plugins.ini"
findstr /C:"demo_toolkit_daynight.amxx" "%P%\configs\plugins.ini" >nul 2>&1 || echo demo_toolkit_daynight.amxx>> "%P%\configs\plugins.ini"
echo [ok] installed into %G%
goto :eof

:done
echo.
echo Test in game console:  amxx plugins
echo Console: amx_record amx_stop amx_dtk ^| dtk_time day^|dusk^|night^|random
echo Chat:    /rec /stop /status /spot /gospot ^| /day /dusk /night
endlocal
