@echo off
rem ============================================================
rem  Launch CS:GO (legacy) through HLAE (csgoLauncher).
rem  Использование: hlae\csgo.bat
rem  В игре: F9 = mirv_streams_movie (normal/depth-EXR/matte),
rem  F10 = стоп записи; пресеты F11 = hud_separate, cinema.
rem ============================================================
setlocal EnableExtensions
set HLAE=D:\HLAE\hlae.exe
if not exist "%HLAE%" (echo [error] %HLAE% not found & exit /b 1)

set CSGO=D:\SteamLibrary\steamapps\common\csgo legacy\csgo.exe
if not exist "%CSGO%" set CSGO=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo.exe
if not exist "%CSGO%" (echo [error] csgo.exe not found & exit /b 1)

echo [hlae] CS:GO via csgoLauncher: %CSGO%
"%HLAE%" -csgoLauncher -noGui -autoStart ^
    -csgoExe "%CSGO%" ^
    -gfxEnabled true -gfxWidth 1920 -gfxHeight 1080 -gfxFull false ^
    -avoidVac true ^
    -customLaunchOptions "+exec movie.cfg"
endlocal
