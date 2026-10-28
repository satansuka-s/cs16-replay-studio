@echo off
rem Build css_extract (CS:S demo -> JSON) using the local css-demo-parser checkout.
setlocal
set VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" set VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat
if not exist "%VCVARS%" (
    echo [ERROR] vcvars64.bat not found.
    exit /b 1
)
call "%VCVARS%" >nul
set NINJA=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja
if exist "%NINJA%\ninja.exe" set PATH=%NINJA%;%PATH%
set ROOT=%~dp0
cmake -S "%ROOT%css_extract" -B "%ROOT%css_extract\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || exit /b 1
cmake --build "%ROOT%css_extract\build" || exit /b 1
echo.
echo OK: %ROOT%css_extract\build\css_extract.exe
endlocal
