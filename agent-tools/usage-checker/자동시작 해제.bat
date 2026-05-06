@echo off
chcp 65001 > nul
SET STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
SET SHORTCUT=%STARTUP%\AI 사용량.lnk

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [해제 완료] 자동 실행 등록이 제거되었습니다.
) else (
    echo [정보] 등록된 자동 실행 항목이 없습니다.
)
echo.
pause
