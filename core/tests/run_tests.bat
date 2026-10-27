@echo off
rem cs16db pipeline tests: build core, synthetic demo roundtrip, stub import into Blender.
setlocal
set ROOT=%~dp0..\..
set BLENDER=D:\Blender\blender.exe
if not exist "%BLENDER%" set BLENDER=blender

echo === 1. Build core ===
call "%ROOT%\core\build.bat" || exit /b 1
set EXE=%ROOT%\core\demo_extract\build\demo_extract.exe

echo.
echo === 2. Synthetic demo roundtrip ===
python "%ROOT%\core\tools\make_demo.py" "%ROOT%\demos\synthetic.dem" || exit /b 1
"%EXE%" "%ROOT%\demos\synthetic.dem" "%ROOT%\core\tests\synthetic.json" || exit /b 1

echo.
echo === 3. Stub JSON for import branches ===
python "%ROOT%\core\tools\make_stub.py" || exit /b 1
"%BLENDER%" --background --python "%ROOT%\blender\blender_import.py" -- ^
    --json "%ROOT%\core\tests\stub.json" --out "%ROOT%\core\tests\stub.blend" --mirror-yaw --flip-pitch
if not exist "%ROOT%\core\tests\stub.blend" (
    echo [FAIL] stub.blend was not created
    exit /b 1
)

echo.
echo === 4. Real demos in demos\ (optional) ===
for %%F in ("%ROOT%\demos\*.dem") do (
    echo   %%F
    "%EXE%" "%%F" "%ROOT%\core\tests\%%~nF.json" --cam-only
)

echo.
echo === ALL TESTS PASSED ===
endlocal
