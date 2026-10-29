@echo off
rem ============================================================
rem  云极智能拆版 V1.2 · Windows 一键打包安装包脚本
rem  用法：双击本文件，依次生成：
rem     dist\云极智能拆版V1.2.exe        （主程序，单文件）
rem     云极智能拆版V1.2-安装包.exe      （NSIS 安装器，含桌面快捷方式勾选）
rem  前置：已安装 Python 3.9+；NSIS 3.x（可选，用于生成安装器）
rem ============================================================
chcp 65001 >nul
cd /d %~dp0

echo [1/5] 检查 Python ...
python --version >nul 2>&1 || (echo 未检测到 Python，请先安装：https://python.org & pause & exit /b 1)

echo [2/5] 安装依赖（首次较慢）...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/5] 安装打包工具 PyInstaller ...
python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [4/5] 编译主程序 EXE（约 2-5 分钟）...
python -m PyInstaller --noconfirm --clean build.spec

echo [5/5] 生成 NSIS 安装包 ...
where makensis >nul 2>&1
if %errorlevel%==0 (
    makensis /V2 installer.nsi
    echo 安装包已生成：云极智能拆版V1.2-安装包.exe
) else (
    echo 未检测到 NSIS（https://nsis.sourceforge.io），跳过安装包。
    echo 主程序已生成：dist\云极智能拆版V1.2.exe
)

echo.
echo 完成！建议在 Windows 10/11 64 位运行；杀毒软件误报请添加信任
pause
