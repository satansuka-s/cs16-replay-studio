@echo off
rem ============================================================
rem  CS 1.6 -> Blender: one-button full replay (map+textures+players+anim)
rem  Usage: make_replay.bat [demo.dem]  (or drop demo onto the batch file)
rem ============================================================
setlocal EnableExtensions
set ROOT=%~dp0

rem ---- configuration (edit if needed) ----
set GAME=D:\Counter-Strike Build 4554
if exist "D:\CS 1.6 GoldClient\cstrike\cstrike.exe" set GAME=D:\CS 1.6 GoldClient
set BLENDER=D:\Blender\blender.exe
if not exist "%BLENDER%" set BLENDER=blender
set PYTHON=python
set DEMO=%1
if "%DEMO%"=="" set DEMO=%ROOT%\demos\synthetic.dem
if not exist "%DEMO%" (
    echo [error] demo not found: %DEMO%
    exit /b 1
)

set WORK=%ROOT%\core\tests\replay_work
set EXE=%ROOT%\core\demo_extract\build\demo_extract.exe
if not exist "%EXE%" (
    echo [error] demo_extract.exe missing - run core\build.bat first
    exit /b 1
)

mkdir "%WORK%" 2>nul
mkdir "%WORK%\models" 2>nul

echo === [1/4] demo_extract ===
"%EXE%" "%DEMO%" "%WORK%\demo.json" 8
if errorlevel 1 exit /b 1

echo === [2/4] decompile player models (MDL -^> SMD + anims + textures) ===
for /d %%M in ("%GAME%\cstrike\models\player\*") do (
    set MNAME=%%~nxM
    if exist "%%M\%%~nxM.mdl" (
        echo   %%M
        "%PYTHON%" "%ROOT%\core\tools\mdl2smd.py" "%%M\%%~nxM.mdl" "%WORK%\models\mdl_%%~nxM" >nul 2>&1
    )
)

echo === [3/4] build Blender scene (map + players + camera) ===
"%BLENDER%" --background --python "%ROOT%\blender\replay_import.py" -- ^
    "--demo-json=%WORK%\demo.json" ^
    "--game=%GAME%" ^
    "--models-dir=%WORK%\models" ^
    "--out=%ROOT%\demos\replay_export.blend" ^
    "--tex-dir=%WORK%\map_tex"
if errorlevel 1 exit /b 1

echo === [4/4] done ===
echo   Scene:        %ROOT%\demos\replay_export.blend
echo   Camera JSON:  %WORK%\demo.json  (for After Effects: ae\import_camera.jsx)
echo   Textures:     %WORK%\map_tex
endlocal
