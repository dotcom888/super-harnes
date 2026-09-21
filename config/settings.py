# -*- coding: utf-8 -*-
"""
config/settings.py: 全局环境配置与路径定义
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# 模型配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# MCP 服务配置文件检索路径（优先 config/ 目录，回退至根目录）
MCP_CONFIG_PATH = WORKSPACE_ROOT / "config" / "mcp_servers.json"
if not MCP_CONFIG_PATH.exists():
    MCP_CONFIG_PATH = WORKSPACE_ROOT / "mcp_servers.json"

# 历史会话归档目录
HISTORY_DIR = WORKSPACE_ROOT / "history"
# Agent 运行与预算配置
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "30"))
AGENT_TOTAL_BUDGET = int(os.getenv("AGENT_TOTAL_BUDGET", "64000"))
