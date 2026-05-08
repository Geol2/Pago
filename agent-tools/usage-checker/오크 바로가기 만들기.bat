@echo off
chcp 65001 > nul
SET TARGET=%~dp0Claude오크.vbs
SET DESKTOP=%USERPROFILE%\Desktop
SET SHORTCUT=%DESKTOP%\Claude 오크.lnk

if not exist "%TARGET%" (
    echo [실패] Claude오크.vbs 가 없습니다: %TARGET%
    pause
    exit /b 1
)

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.Description='Claude 오크 위젯'; $s.WindowStyle=7; $s.Save()"

echo.
echo [완료] 바탕화면에 "Claude 오크" 바로가기가 생성됐습니다.
echo   %SHORTCUT%
echo.
echo 이제 바탕화면 아이콘을 더블클릭하면 위젯이 실행됩니다.
echo.
pause
