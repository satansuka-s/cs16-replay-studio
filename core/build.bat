@echo off
rem Build demo_extract (HLDemo + net decoder) with MSVC Build Tools via Ninja.
rem Adjust VCVARS path if your Visual Studio is installed elsewhere.
setlocal

set VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" set VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" (
    echo [ERROR] vcvars64.bat not found. Install MSVC Build Tools or edit build.bat.
    exit /b 1
)

call "%VCVARS%" >nul
set NINJA=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja
if exist "%NINJA%\ninja.exe" set PATH=%NINJA%;%PATH%

set ROOT=%~dp0
set SRC=%ROOT%demo_extract
set BUILD=%ROOT%demo_extract\build

cmake -S "%SRC%" -B "%BUILD%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || exit /b 1
cmake --build "%BUILD%" || exit /b 1

echo.
echo OK: %BUILD%\demo_extract.exe
endlocal
