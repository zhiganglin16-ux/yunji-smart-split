# -*- coding: utf-8 -*-
"""云极智能拆版 V1.2 安装包打包脚本：把生成的 NSIS 安装器 exe 压成单个 zip。
zip 内条目使用中文名（UTF-8 标志），Windows 资源管理器解压后即为
「云极智能拆版V1.2-安装包.exe」。
"""
import glob
import os
import sys
import zipfile

OUT_ZIP = "云极智能拆版V1.2-安装包.zip"
ARC_NAME = "云极智能拆版V1.2-安装包.exe"

def main() -> int:
    exes = [f for f in glob.glob("*.exe") if "uninstall" not in f.lower()]
    print("FOUND EXE:", exes, flush=True)
    if not exes:
        print("ERROR: no installer exe found in workspace root", file=sys.stderr)
        return 1
    src = exes[0]
    if os.path.exists(OUT_ZIP):
        os.remove(OUT_ZIP)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, ARC_NAME)
    print("ZIP OK:", OUT_ZIP, os.path.getsize(OUT_ZIP), "bytes", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
