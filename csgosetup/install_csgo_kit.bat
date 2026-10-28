@echo off
rem ============================================================
rem  Installs the CS:GO cinema kit (movie.cfg + mirv_streams preset)
rem  into the CS:GO install. Choose the game dir below or pass it:
rem    install_csgo_kit.bat ["D:\path\to\csgo"]
rem ============================================================
setlocal
set ROOT=%~dp0
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\SteamLibrary\steamapps\common\csgo legacy\csgo" set GAME=D:\SteamLibrary\steamapps\common\csgo legacy
    if not exist "%GAME%\csgo" if exist "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo" set GAME=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive
    if not exist "%GAME%\csgo" if exist "D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\csgo" set GAME=D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive
)
if not exist "%GAME%\csgo\cfg" (
    echo [error] csgo\cfg not found in %GAME%
    exit /b 1
)
set CFG=%GAME%\csgo\cfg

echo == backups ==
if exist "%CFG%\movie.cfg" copy /y "%CFG%\movie.cfg" "%CFG%\movie.cfg.cs16db.bak" >nul && echo   movie.cfg -^> movie.cfg.cs16db.bak
if exist "%CFG%\mirv_streams_movie.cfg" copy /y "%CFG%\mirv_streams_movie.cfg" "%CFG%\mirv_streams_movie.cfg.cs16db.bak" >nul && echo   mirv_streams_movie.cfg -^> .bak

echo == install ==
copy /y "%ROOT%movie.cfg" "%CFG%\movie.cfg" >nul
copy /y "%ROOT%mirv_streams_movie.cfg" "%CFG%\mirv_streams_movie.cfg" >nul
echo   movie.cfg, mirv_streams_movie.cfg installed.

echo == autoexec hook (exec movie.cfg at start) ==
if not exist "%CFG%\autoexec.cfg" (
    echo exec movie.cfg > "%CFG%\autoexec.cfg"
    echo   autoexec.cfg created
) else (
    findstr /c:"exec movie.cfg" "%CFG%\autoexec.cfg" >nul 2>&1 || echo exec movie.cfg>> "%CFG%\autoexec.cfg"
    echo   autoexec.cfg hooked
)
echo done: %CFG%
endlocal
