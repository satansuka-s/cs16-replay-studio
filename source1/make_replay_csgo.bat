@echo off
rem ============================================================
rem  CS:GO (Source 1) -> Blender: one-button replay
rem  players + camera + kill/round edit markers from the demo.
rem  The map itself needs SourceIO (Blender 4.x), see README.md.
rem  Usage: make_replay_csgo.bat [demo.dem] [followUserID]
rem ============================================================
setlocal EnableExtensions
set ROOT=%~dp0..

rem ---- configuration (edit if needed) ----
set CSGO_DIR=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive
set BLENDER=D:\Blender\blender.exe
if not exist "%BLENDER%" set BLENDER=blender

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

echo === [1/3] csgo_extract (demo -^> JSON: players + camera + kill/round events) ===
if "%FOLLOW%"=="" (
    "%EXE%" "%DEMO%" "%WORK%\demo.json"
) else (
    "%EXE%" "%DEMO%" "%WORK%\demo.json" --follow %FOLLOW%
)
if errorlevel 1 exit /b 1

echo === [2/3] build Blender scene (players placeholders + camera + markers) ===
"%BLENDER%" --background --python "%ROOT%\blender\replay_import.py" -- ^
    "--demo-json=%WORK%\demo.json" ^
    "--game=%CSGO_DIR%" ^
    "--out=%ROOT%\demos\csgo_replay.blend" ^
    "--tex-dir=%WORK%\map_tex" ^
    "--cam-spline"
if errorlevel 1 exit /b 1

echo === [3/3] done ===
echo   Scene:        %ROOT%\demos\csgo_replay.blend
echo   Camera JSON:  %WORK%\demo.json  (After Effects: ae\import_camera.jsx)
echo   Map:          import with SourceIO in Blender 4.x (de_%mapname%.bsp lives inside csgo\maps)
endlocal
