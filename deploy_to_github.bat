@echo off
rem ============================================================
rem  Deploy cs16-replay-studio to a remote git host in one command.
rem  Usage:
rem    deploy_to_github.bat  https://github.com/YOUR_USER/cs16-replay-studio.git
rem    deploy_to_github.bat  https://gitlab.com/YOUR_USER/cs16-replay-studio.git
rem  Requirements: existing (empty) remote repository.
rem  The gh CLI is already authenticated on this machine (login:
rem  satansuka-s) and has 'repo' scope - pushing works even though
rem  creating new repos is blocked for the account (trade controls).
rem ============================================================
setlocal
set ROOT=%~dp0
set URL=%~1
if "%URL%"=="" (
    echo usage: %~nx0 https://host/user/repo.git
    exit /b 1
)
cd /d "%ROOT%"
git remote remove origin 2>nul
git remote add origin "%URL%"
git push -u origin master:master
if errorlevel 1 (
    echo [error] push failed - check URL and credentials
    exit /b 1
)
echo done: %URL%
endlocal
