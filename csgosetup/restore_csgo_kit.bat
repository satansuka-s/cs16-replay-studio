@echo off
rem Restores the CS:GO movie.cfg backups made by install_csgo_kit.bat
setlocal
set GAME=%~1
if "%GAME%"=="" (
    if exist "D:\SteamLibrary\steamapps\common\csgo legacy\csgo" set GAME=D:\SteamLibrary\steamapps\common\csgo legacy
    if not exist "%GAME%\csgo" if exist "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo" set GAME=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive
)
set CFG=%GAME%\csgo\cfg
if not exist "%CFG%\movie.cfg.cs16db.bak" (
    echo [info] no backup found, nothing to restore
    exit /b 0
)
copy /y "%CFG%\movie.cfg.cs16db.bak" "%CFG%\movie.cfg" >nul
if exist "%CFG%\mirv_streams_movie.cfg.cs16db.bak" copy /y "%CFG%\mirv_streams_movie.cfg.cs16db.bak" "%CFG%\mirv_streams_movie.cfg" >nul
echo restored %CFG%
endlocal
