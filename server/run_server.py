# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# 支持以脚本解释器模式直接运行子进程（如 MCP 服务脚本）
if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
    script_path = Path(sys.argv[1]).resolve()
    sys.argv = sys.argv[1:]
    import runpy
    runpy.run_path(str(script_path), run_name="__main__")
    sys.exit(0)

# 动态定位项目或打包根目录
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from server.app import app

def main():
    port = 8765
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    print(f"Starting Super-Harnes Agent Backend on http://127.0.0.1:{port}...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()
