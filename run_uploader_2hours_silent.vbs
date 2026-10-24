Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\ProjekAntigravity\ENCLip"
WshShell.Run "cmd /c ""D:\ProjekAntigravity\ENCLip\run_uploader_2hours.bat""", 0, False
