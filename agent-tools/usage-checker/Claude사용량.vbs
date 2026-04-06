' Claude Code 사용량 위젯 실행기 (Windows - 콘솔 창 없이 실행)
Dim fso, scriptDir, pyScript, cmd

fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\claude_usage_checker.py"

' pythonw.exe 로 실행하면 검은 콘솔 창이 뜨지 않음
cmd = "pythonw.exe """ & pyScript & """ --desktop"

CreateObject("WScript.Shell").Run cmd, 0, False
