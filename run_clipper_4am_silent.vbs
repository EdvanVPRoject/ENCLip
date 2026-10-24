Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\ProjekAntigravity\ENCLip"
WshShell.Run "cmd /c ""D:\ProjekAntigravity\ENCLip\run_clipper_4am.bat""", 0, False
