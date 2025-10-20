Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c start_auto_backup.bat", 0, False
Set WshShell = Nothing
