Dim fso, shell, env, scriptDir, pyScript, logFile, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
Set env = shell.Environment("Process")

' set 명령은 값 뒤 공백까지 환경변수에 포함되는 함정이 있어 VBS 환경 API로 직접 설정
env("PYTHONUTF8") = "1"

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\claude_usage.py"
logFile  = scriptDir & "\vbs_error.log"

' python.exe(콘솔 있음)을 숨김 창으로 실행 — pythonw와 달리 import 에러를 로그로 남길 수 있음
cmd = "cmd /c python.exe """ & pyScript & """ --tray > """ & logFile & """ 2>&1"

shell.Run cmd, 0, False
