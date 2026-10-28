@echo off
rem ============================================================
rem  Installs the CS:S cinema kit (movie.cfg + HLAE screen preset)
rem  into the Counter-Strike: Source install.
rem    install_css_kit.bat ["D:\path\to\Counter-Strike Source"]
rem ============================================================
setlocal
set ROOT=%~dp0
set GAME=%~1
if "%GAME%"=="" (
    if exist "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source\cstrike" set GAME=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source
    if not exist "%GAME%\cstrike" if exist "C:\Games\Counter-Strike Source\cstrike" set GAME=C:\Games\Counter-Strike Source
)
if not exist "%GAME%\cstrike\cfg" (
    echo [error] cstrike\cfg not found in %GAME% - is CS:S fully installed?
    exit /b 1
)
set CFG=%GAME%\cstrike\cfg

if exist "%CFG%\movie.cfg" copy /y "%CFG%\movie.cfg" "%CFG%\movie.cfg.cs16db.bak" >nul && echo   backup movie.cfg
if exist "%CFG%\mirv_screen_record.cfg" copy /y "%CFG%\mirv_screen_record.cfg" "%CFG%\mirv_screen_record.cfg.cs16db.bak" >nul && echo   backup mirv preset

copy /y "%ROOT%movie.cfg" "%CFG%\movie.cfg" >nul
copy /y "%ROOT%mirv_screen_record.cfg" "%CFG%\mirv_screen_record.cfg" >nul

if not exist "%CFG%\autoexec.cfg" (
    echo exec movie.cfg > "%CFG%\autoexec.cfg"
) else (
    findstr /c:"exec movie.cfg" "%CFG%\autoexec.cfg" >nul 2>&1 || echo exec movie.cfg>> "%CFG%\autoexec.cfg"
)
echo done: %CFG%
endlocal
