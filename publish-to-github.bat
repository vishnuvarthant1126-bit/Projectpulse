@echo off
rem Pushes this folder to github.com/vishnuvarthant1126-bit/projectpulse.
rem First time: create an EMPTY public repo named "projectpulse" on GitHub (no README), then double-click this.
setlocal
cd /d "%~dp0"
echo Folder: %CD%
rem Find git even if PATH has not refreshed since Git was installed.
set "GIT=git"
where git >NUL 2>&1 && goto havegit
if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe" & goto havegit
if exist "%ProgramFiles(x86)%\Git\cmd\git.exe" set "GIT=%ProgramFiles(x86)%\Git\cmd\git.exe" & goto havegit
if exist "%LocalAppData%\Programs\Git\cmd\git.exe" set "GIT=%LocalAppData%\Programs\Git\cmd\git.exe" & goto havegit
echo GIT NOT FOUND - install it from https://git-scm.com/download/win , restart the computer, then run this again.
goto end
:havegit
"%GIT%" --version
if not exist ".git" (
  "%GIT%" init -b main
  "%GIT%" remote add origin https://github.com/vishnuvarthant1126-bit/projectpulse.git
)
"%GIT%" add -A
"%GIT%" diff --cached --quiet || "%GIT%" commit -m "Update ProjectPulse"
if errorlevel 1 (echo. & echo COMMIT FAILED - set your git name/email first, see the steps in the chat & goto end)
"%GIT%" push -u origin main
if errorlevel 1 (echo. & echo PUSH FAILED - check that github.com/vishnuvarthant1126-bit/projectpulse exists and is empty) else (echo. & echo PUSH OK)
:end
pause
