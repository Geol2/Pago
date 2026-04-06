Dim fso, scriptDir, pyScript, cmd

fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\claude_usage.py"

cmd = "cmd /c set PYTHONUTF8=1 && pythonw.exe """ & pyScript & """ --desktop"

CreateObject("WScript.Shell").Run cmd, 0, False
