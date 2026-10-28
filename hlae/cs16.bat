@echo off
rem ============================================================
rem  Launch CS 1.6 through HLAE (AfxHookGoldSrc) - кино-режим.
rem  Использование:
rem    hlae\cs16.bat                 [Build 4554 по умолчанию]
rem    hlae\cs16.bat "D:\CS 1.6 GoldClient"   (или любой путь к hl.exe)
rem  В игре: консольные mirv_* команды (запись: mirv_recordmovie_start)
rem  и наши movie.cfg (F4-F11, dtk_time day|dusk|night).
rem ============================================================
setlocal EnableExtensions
set HLAE=D:\HLAE\hlae.exe
if not exist "%HLAE%" (echo [error] %HLAE% not found & exit /b 1)

set GAME=%~1
if "%GAME%"=="" set GAME=D:\Counter-Strike Build 4554
set HLEXE=%GAME%\hl.exe
if not exist "%HLEXE%" set HLEXE=%GAME%\cstrike\hl.exe
if not exist "%HLEXE%" (echo [error] hl.exe not found under %GAME% & exit /b 1)

echo [hlae] CS 1.6 via AfxHookGoldSrc: %HLEXE%
"%HLAE%" -afxHookGoldSrc -noGui -autoStart ^
    -gamePath "%HLEXE%" ^
    -modification cstrike ^
    -gfxWidth 1920 -gfxHeight 1080 -renderMode 1 ^
    -customCmdLine "+exec movie.cfg"
endlocal
