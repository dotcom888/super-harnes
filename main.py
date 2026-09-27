# -*- coding: utf-8 -*-
"""
main.py: 统一启动入口
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

AGENT_HOME = Path(__file__).resolve().parent
if str(AGENT_HOME) not in sys.path:
    sys.path.insert(0, str(AGENT_HOME))

# 优先载入用户当前目标工作区的 .env；若不存在或缺失键，回退载入 Agent 安装根目录的 .env
load_dotenv()
agent_env = AGENT_HOME / ".env"
if agent_env.exists():
    load_dotenv(dotenv_path=agent_env)

from cli.console import main

if __name__ == "__main__":
    main()
