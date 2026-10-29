; ============================================================
; 云极智能拆版 V1.2 · NSIS 安装脚本
; 要求：已先用 PyInstaller 生成 dist\云极智能拆版V1.2.exe
; 安装时提供"创建桌面快捷方式"勾选框（默认勾选）
; ============================================================
Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

Name "云极智能拆版"
OutFile "setup-yunji-v1.2.exe"
InstallDir "$PROGRAMFILES64\云极科技\云极智能拆版"
RequestExecutionLevel admin

; 品牌图标
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\云极智能拆版V1.2.exe"
!define MUI_FINISHPAGE_RUN_TEXT "立即运行云极智能拆版"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "查看使用说明"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\使用说明.txt"

; ---------- 页面 ----------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Var CreateDesktopShortcut

; ---------- 组件（勾选框） ----------
Section "主程序（必需）" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "dist\云极智能拆版V1.2.exe"
  File "使用说明.txt"
  ; 开始菜单快捷方式
  CreateDirectory "$SMPROGRAMS\云极科技"
  CreateShortcut "$SMPROGRAMS\云极科技\云极智能拆版.lnk" "$INSTDIR\云极智能拆版V1.2.exe"
  WriteUninstaller "$INSTDIR\卸载云极智能拆版.exe"
  ; 卸载信息
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "DisplayName" "云极智能拆版"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "DisplayIcon" "$INSTDIR\云极智能拆版V1.2.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "UninstallString" "$INSTDIR\卸载云极智能拆版.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "DisplayVersion" "1.2"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "Publisher" "云极科技"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版" "InstallLocation" "$INSTDIR"
SectionEnd

Section "创建桌面快捷方式" SecDesktop
  SectionIn 1
  CreateShortcut "$DESKTOP\云极智能拆版.lnk" "$INSTDIR\云极智能拆版V1.2.exe"
SectionEnd

; ---------- 卸载 ----------
Section "Uninstall"
  Delete "$INSTDIR\云极智能拆版V1.2.exe"
  Delete "$INSTDIR\使用说明.txt"
  Delete "$INSTDIR\卸载云极智能拆版.exe"
  Delete "$DESKTOP\云极智能拆版.lnk"
  Delete "$SMPROGRAMS\云极科技\云极智能拆版.lnk"
  RMDir "$INSTDIR"
  RMDir "$SMPROGRAMS\云极科技"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\云极智能拆版"
SectionEnd
