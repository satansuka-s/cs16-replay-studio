@echo off
rem ============================================================
rem  CS:GO / CS:S (Source 1) -> Blender: one-button replay
rem  map (own Source BSP importer + VMT/VTF textures) + players +
rem  camera + kill/round edit markers from the demo.
rem  Usage: make_replay_csgo.bat [demo.dem] [followUserID]
rem ============================================================
setlocal EnableExtensions
set ROOT=%~dp0..

rem ---- configuration (edit if needed) ----
rem game dir auto-detect: prefer CS:GO legacy build, then steam CS:GO,
rem then CS:S / Source SDK based installs
set CSGO_DIR=D:\SteamLibrary\steamapps\common\csgo legacy
if not exist "%CSGO_DIR%\csgo\maps" set CSGO_DIR=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive
if not exist "%CSGO_DIR%\csgo\maps" set CSGO_DIR=D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive
if not exist "%CSGO_DIR%\csgo\maps" set CSGO_DIR=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source
set BLENDER=D:\Blender\blender.exe
if not exist "%BLENDER%" set BLENDER=blender
set PYTHON=python

set DEMO=%1
if "%DEMO%"=="" set DEMO=%ROOT%\core\extern\demoinfogo\test-data\ok.dem
if not exist "%DEMO%" (
    echo [error] demo not found: %DEMO%
    exit /b 1
)
set FOLLOW=%2

set WORK=%ROOT%\core\tests\csgo_work
set EXE=%ROOT%\source1\go_extract\csgo_extract.exe
if not exist "%EXE%" (
    echo [error] csgo_extract.exe missing - build with:  cd source1\go_extract ^&^& go build -o csgo_extract.exe .
    exit /b 1
)

mkdir "%WORK%" 2>nul

echo === [1/4] csgo_extract (demo -^> JSON: players + camera + kill/round events) ===
if "%FOLLOW%"=="" (
    "%EXE%" "%DEMO%" "%WORK%\demo.json"
) else (
    "%EXE%" "%DEMO%" "%WORK%\demo.json" --follow %FOLLOW%
)
if errorlevel 1 exit /b 1

echo === [2/4] extract map textures (VMT+VTF -^> PNG, via own decoder) ===
set MAPNAME=
for /f "usebackq delims=" %%M in (`%PYTHON% -c "import json;print(json.load(open(r'%WORK%\demo.json',encoding='utf-8'))['map'])"`) do set MAPNAME=%%M
echo   map: %MAPNAME%  game: %CSGO_DIR%
if "%MAPNAME%"=="" exit /b 1
mkdir "%WORK%\map_tex" 2>nul
%PYTHON% "%ROOT%\core\tools\source1_tex.py" "%CSGO_DIR%\csgo\maps\%MAPNAME%.bsp" --game "%CSGO_DIR%" --out "%WORK%\map_tex"
if errorlevel 1 exit /b 1

echo === [3/4] build Blender scene (map + players + camera + markers) ===
"%BLENDER%" --background --python "%ROOT%\blender\replay_import.py" -- ^
    "--demo-json=%WORK%\demo.json" ^
    "--game=%CSGO_DIR%" ^
    "--out=%ROOT%\demos\csgo_replay.blend" ^
    "--tex-dir=%WORK%\map_tex" ^
    "--cam-spline"
if errorlevel 1 exit /b 1

echo === [4/4] done ===
echo   Scene:        %ROOT%\demos\csgo_replay.blend
echo   Camera JSON:  %WORK%\demo.json  (After Effects: ae\import_camera.jsx)
echo   Map:          imported from %MAPNAME%.bsp by own importer (no addons)
endlocal
