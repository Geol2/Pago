Dim fso, shell, env, scriptDir, pyScript, logFile, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
Set env = shell.Environment("Process")

' UTF-8 (set 명령은 공백 함정 있어 환경 API 사용)
env("PYTHONUTF8") = "1"

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\claude_usage.py"
logFile  = scriptDir & "\orc_widget.log"

' 콘솔창 없이 백그라운드 실행 — 에러는 로그로
cmd = "cmd /c python.exe """ & pyScript & """ --orc > """ & logFile & """ 2>&1"

shell.Run cmd, 0, False
