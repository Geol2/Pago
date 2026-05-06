@echo off
chcp 65001 > nul
SET TARGET=%~dp0Claude사용량.vbs
SET STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
SET SHORTCUT=%STARTUP%\AI 사용량.lnk

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.Description='Claude 사용량 트레이'; $s.Save()"

echo.
echo [등록 완료] 다음 부팅부터 자동 실행됩니다.
echo   %SHORTCUT%
echo.
pause
