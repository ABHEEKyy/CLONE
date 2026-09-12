Set WshShell = CreateObject("WScript.Shell")
' 0 hides the window completely, False runs it asynchronously
WshShell.Run "cmd /c cd /d """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & """ && py hybrid_listener.py", 0, False
Set WshShell = Nothing

