@echo off
rem ============================================================
rem  Launch CS:S through HLAE (customLoader + AfxHookSource).
rem  Для CS:S доступен только «screen record» (mirv_streams record
rem  screen + host_framerate) - см. cssetup\mirv_screen_record.cfg (F9).
rem  Использование: hlae\css.bat
rem ============================================================
setlocal EnableExtensions
set HLAE=D:\HLAE\hlae.exe
if not exist "%HLAE%" (echo [error] %HLAE% not found & exit /b 1)

set CSS=D:\Counter-Strike Source
set HLEXE=%CSS%\hl2.exe
if not exist "%HLEXE%" (echo [error] hl2.exe not found in %CSS% & exit /b 1)

echo [hlae] CS:S via customLoader (AfxHookSource, screen record mode): %HLEXE%
"%HLAE%" -customLoader -noGui -autoStart ^
    -hookDllPath "D:\HLAE\AfxHookSource.dll" ^
    -programPath "%HLEXE%" ^
    -cmdLine "-game cstrike +exec movie.cfg"
endlocal
