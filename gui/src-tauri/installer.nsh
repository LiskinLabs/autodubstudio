; AutoDub Studio — NSIS Installer Hooks
; Cleans old resources before installing new ones

!macro preInstall
  ; Delete old resource directory to force clean extraction
  RMDir /r "$INSTDIR\_up_"
!macroend

!macro customInstall
  ; Remove stale Python cache files from previous install
  RMDir /r "$INSTDIR\_up_\__pycache__"
  Delete "$INSTDIR\_up_\*.pyc"
!macroend
