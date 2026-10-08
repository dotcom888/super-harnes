# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# 强制将项目根目录加入 sys.path
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
