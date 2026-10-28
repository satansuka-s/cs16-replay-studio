@echo off
rem ============================================================
rem  cs16db - local HLTV recording (the "pro" demo route)
rem  HLTV records the whole match with exact positions of all
rem  players (protocol 48 - fully supported by our pipeline).
rem
rem  1) Start CS 1.6 and host a game (or run a dedicated server).
rem  2) Run: record_hltv.bat [server_ip:port]   (default 127.0.0.1:27015)
rem  3) Stop HLTV (close its window) - demo is saved next to hltv.exe
rem  4) Feed the .dem into make_replay.bat  (choose HLTV demo in the menu)
rem ============================================================
setlocal EnableExtensions
set ROOT=%~dp0
set SERVER=%1
if "%SERVER%"=="" set SERVER=127.0.0.1:27015
set HLTV=D:\Counter-Strike Build 4554\hltv.exe
if not exist "%HLTV%" (echo [error] hltv.exe not found - use the 4554 install & exit /b 1)

rem ship the cfg next to hltv (HLTV executes its cfg from the game dir)
if not exist "D:\Counter-Strike Build 4554\cstrike\hltv_movie.cfg" copy /y "%ROOT%hltv_movie.cfg" "D:\Counter-Strike Build 4554\cstrike\hltv_movie.cfg" >nul

echo Connecting %HLTV% to %SERVER% - recording cs16_match.dem
echo Close the HLTV console window to stop recording.
"%HLTV%" -port 27020 +exec hltv_movie.cfg +connect %SERVER%
endlocal
