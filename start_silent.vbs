Set WshShell = CreateObject("WScript.Shell")
strScriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptPath

' Set absolute paths for PYTHONPATH so source code wins over site-packages
strBaseDir = strScriptPath & "\"
strPythonPath = strBaseDir & "aw-core;" & strBaseDir & "aw-client;" & strBaseDir & "aw-server;" & strBaseDir & "aw-watcher-afk;" & strBaseDir & "aw-watcher-window;" & strBaseDir & "aw-watcher-input;" & strBaseDir & "aw-pywebview"
WshShell.Environment("PROCESS")("PYTHONPATH") = strPythonPath

' Start the application silently using pythonw from source imports
WshShell.Run "cmd /c .venv\Scripts\pythonw.exe -m aw_pywebview", 0, False
