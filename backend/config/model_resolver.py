# -*- coding: utf-8 -*-
"""
config/model_resolver.py: 统一模型与凭据解析引擎
实现 CLI 命令行终端与桌面端 (Electron) 实时无缝同步，同时保证 Git 源码仓库 100% 零硬编码、零敏感泄露。
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("config.model_resolver")

USER_DATA_ROOT = Path.home() / ".super-harness"
USER_CONFIG_DIR = USER_DATA_ROOT / "config"
USER_MODELS_CONFIG_PATH = USER_CONFIG_DIR / "models_config.json"
LEGACY_DATA_ROOT = Path.home() / ".super-harnes"
LEGACY_MODELS_CONFIG_PATH = LEGACY_DATA_ROOT / "config" / "models_config.json"


def get_user_models_config_path() -> Path:
    """获取用户中央模型配置存储路径（位于用户家目录下，绝对脱离 Git 仓库，确保源码推送安全）"""
    return USER_MODELS_CONFIG_PATH


def clean_base_url(url: str, protocol: str = "openai_chat") -> str:
    """标准化清理用户填写的 Base URL，自动剔除首尾空格、尾部斜杠及误填的具体 API 端点后缀"""
    if not url:
        return ""
    clean = url.strip()
    clean = re.sub(r"/+$", "", clean)
    for suffix in [
        "/chat/completions",
        "/completions",
        "/v1/chat/completions",
        "/messages",
        "/v1/messages",
        "/responses",
        "/v1/responses"
    ]:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)].rstrip("/")
            break
    return clean


def load_user_models_config() -> Dict[str, Any]:
    """读取用户中央模型配置文件"""
    target_path = USER_MODELS_CONFIG_PATH if USER_MODELS_CONFIG_PATH.exists() else LEGACY_MODELS_CONFIG_PATH
    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"读取用户中央模型配置异常: {e}")
    return {"current_model": "", "providers": []}


def resolve_active_model_config(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> Tuple[str, str, str, str]:
    """
    统一解析当前运行所需的大模型名称、API 密钥与接口地址。

    优先级规则：
    1. 显式指定参数（命令行 --model 或代码构造入参）
    2. 局部环境变量 / 工作区 .env（若配置了有效非空的 LLM_API_KEY）
    3. 桌面端已同步的用户中央配置 (~/.super-harness/config/models_config.json)
    4. 兜底默认值

    返回: (resolved_model, resolved_api_key, resolved_base_url, source_info)
    """
    user_cfg = load_user_models_config()
    desktop_model = user_cfg.get("current_model", "").strip()
    providers: List[Dict[str, Any]] = user_cfg.get("providers", [])

    # 1. 检查环境变量中是否提供了真正的 API Key (过滤占位符)
    env_key = os.getenv("LLM_API_KEY", "").strip()
    if env_key == "your_api_key_here":
        env_key = ""

    # 2. 确定目标模型名称
    env_model = os.getenv("LLM_MODEL", "").strip()
    if model:
        target_model = model
    elif not env_key and desktop_model:
        # 当 .env 未填写有效 Key 时，优先对齐桌面端当前激活模型
        target_model = desktop_model
    elif env_model:
        target_model = env_model
    elif desktop_model:
        target_model = desktop_model
    else:
        target_model = "deepseek-chat"

    # 3. 尝试从桌面端 providers 寻找匹配该模型的提供方配置 (大小写与空白自适应容错)
    matched_provider = None
    target_model_clean = target_model.strip()
    if providers:
        # 3.1 精确匹配模型名
        for p in providers:
            p_models = [m.strip() for m in p.get("models", [])]
            if target_model_clean in p_models:
                p_key = p.get("api_key", "").strip()
                if p_key:
                    matched_provider = p
                    break

        # 3.2 大小写不敏感匹配
        if not matched_provider:
            for p in providers:
                p_models_lower = [m.strip().lower() for m in p.get("models", [])]
                if target_model_clean.lower() in p_models_lower:
                    p_key = p.get("api_key", "").strip()
                    if p_key:
                        matched_provider = p
                        break

        # 3.3 兜底回退：若未配置指定模型但有可用有效 Key 的 Provider，优先借用有效 Provider 凭据
        if not matched_provider and not env_key:
            for p in providers:
                p_key = p.get("api_key", "").strip()
                p_models = p.get("models", [])
                if p_key:
                    matched_provider = p
                    if not model:
                        target_model = desktop_model if (desktop_model and desktop_model in p_models) else (p_models[0] if p_models else target_model)
                    break

    # 4. 提取提供方密钥与 Base URL
    provider_key = ""
    provider_url = ""
    if matched_provider:
        raw_key = matched_provider.get("api_key", "").strip()
        if raw_key.startswith("${") and raw_key.endswith("}"):
            raw_key = os.getenv(raw_key[2:-1], "").strip()
        elif raw_key.startswith("$"):
            raw_key = os.getenv(raw_key[1:], "").strip()
        provider_key = raw_key
        raw_url = matched_provider.get("base_url", "").strip()
        provider_url = clean_base_url(raw_url, matched_provider.get("protocol", "openai_chat"))

    # 5. 组合参数：如果密钥来自桌面端提供方，则优先使用该提供方配置的专用 Base URL
    explicit_key = (api_key or "").strip()
    explicit_url = (base_url or "").strip()

    if explicit_key:
        final_key = explicit_key
        final_url = explicit_url or os.getenv("LLM_BASE_URL", "").strip() or provider_url or "https://api.deepseek.com"
        source = "调用参数指定"
    elif env_key:
        final_key = env_key
        final_url = explicit_url or os.getenv("LLM_BASE_URL", "").strip() or provider_url or "https://api.deepseek.com"
        source = "工作区/环境变量 (.env)"
    elif provider_key:
        final_key = provider_key
        final_url = explicit_url or provider_url or os.getenv("LLM_BASE_URL", "").strip() or "https://api.deepseek.com"
        source = "桌面端配置 (~/.super-harness/config/models_config.json)"
    else:
        final_key = ""
        final_url = explicit_url or os.getenv("LLM_BASE_URL", "").strip() or "https://api.deepseek.com"
        source = "未配置"

    final_url = clean_base_url(final_url)
    return target_model, final_key, final_url, source
