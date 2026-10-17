from server.project_utils import resolve_project_workspace_root, register_project_path, AGENT_SOURCE_ROOT, get_registered_projects
# -*- coding: utf-8 -*-
"""
server/app.py: FastAPI 服务端 (为 Electron 客户端提供多项目历史扫描、自定义模型映射与 AUTO 模式通信)
"""
import os
import re
import sys
import json
import time
import asyncio
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel

# 确保项目根目录在 sys.path (支持 PyInstaller 打包与冻结运行)
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
import urllib.parse

logger = logging.getLogger("server")
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from server.attachment_parser import detect_attachment_type, extract_attachment_summary

from server.agent_bridge import bridge, format_tool_display
from tools.framework.workspace import default_workspace, set_workspace_root
from tools.framework.policies import default_policy
from skills import default_skill_manager

app = FastAPI(title="Super-Harness Agent Desktop API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_DATA_ROOT = Path.home() / ".super-harness"
USER_DATA_ROOT.mkdir(parents=True, exist_ok=True)
USER_CONFIG_DIR = USER_DATA_ROOT / "config"
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
USER_MODELS_CONFIG_PATH = USER_CONFIG_DIR / "models_config.json"

MODELS_CONFIG_PATH = ROOT_DIR / "config" / "models_config.json"
USER_HISTORY_ROOT = USER_DATA_ROOT / "history"
USER_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)

# 全环境统一使用用户中央历史目录，完全防止污染源码库
HISTORY_ROOT = USER_HISTORY_ROOT

# ================= 数据模型定义 =================
# ================= 附件存储与工作区旧版迁移 =================
def migrate_legacy_attachments(ws_root: Optional[Path]):
    """自动将工作区遗留的旧版 .super-harnes 与 .super_attachments 迁移至 .super-harness 并清理旧目录"""
    if not ws_root:
        return
    try:
        ws_path = Path(ws_root).resolve()
        if not ws_path.exists() or not ws_path.is_dir():
            return
        target_harness = ws_path / ".super-harness"
        target_dir = target_harness / "attachments"
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. 迁移旧版 .super-harnes 到 .super-harness
        legacy_harnes = ws_path / ".super-harnes"
        if legacy_harnes.exists() and legacy_harnes.is_dir():
            for item in list(legacy_harnes.iterdir()):
                dest = target_harness / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
                elif item.is_dir():
                    for sub in list(item.iterdir()):
                        sub_dest = dest / sub.name
                        if not sub_dest.exists():
                            shutil.move(str(sub), str(sub_dest))
            shutil.rmtree(legacy_harnes, ignore_errors=True)

        # 2. 迁移旧版 .super_attachments 到 .super-harness/attachments
        legacy_dir = ws_path / ".super_attachments"
        if legacy_dir.exists() and legacy_dir.is_dir():
            for item in list(legacy_dir.iterdir()):
                dest = target_dir / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
                elif item.is_dir():
                    for sub in list(item.iterdir()):
                        sub_dest = dest / sub.name
                        if not sub_dest.exists():
                            shutil.move(str(sub), str(sub_dest))
            shutil.rmtree(legacy_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"迁移旧版附件/配置目录失败: {e}")


class ApprovalResponseModel(BaseModel):
    ticket_id: str
    approved: bool
    trust_session: Optional[bool] = False

class UserInputResponseModel(BaseModel):
    request_id: str
    selected_option: Optional[str] = ""
    custom_input: Optional[str] = ""

class PermissionModeModel(BaseModel):
    mode: str

class PromptRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    permission_mode: Optional[str] = "auto"
    session_id: Optional[str] = None
    project: Optional[str] = None

class SessionActionRequest(BaseModel):
    session_id: Optional[str] = None
    project: Optional[str] = None

class WorkspaceSwitchRequest(BaseModel):
    path: Optional[str] = None
    name: Optional[str] = None

class WorkspaceAddRequest(BaseModel):
    path: str
    name: Optional[str] = None

class ModelSwitchRequest(BaseModel):
    model: str

class ProviderConfigRequest(BaseModel):
    id: Optional[str] = None
    name: str
    base_url: str
    api_key: str = ""
    models: List[str] = []
    is_custom: bool = True
    protocol: Optional[str] = "openai_chat"

class ModeSwitchRequest(BaseModel):
    mode: str

# ================= 辅助函数：模型与提供方管理 =================
def load_models_config() -> Dict[str, Any]:
    """读取模型与提供方配置 (脱机打包模式严格读取用户数据目录，初始为空白纯净；开发模式允许回退本地开发配置)"""
    candidate_paths = [USER_MODELS_CONFIG_PATH] if getattr(sys, "frozen", False) else [USER_MODELS_CONFIG_PATH, MODELS_CONFIG_PATH]
    for p in candidate_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and "providers" in data:
                        return data
            except Exception:
                pass

    # 仅在当前环境显式配置了真实有效的 LLM_API_KEY 时才自动生成环境提供方
    env_key = os.getenv("LLM_API_KEY", "").strip()
    env_model = os.getenv("LLM_MODEL", "").strip()
    env_base_url = os.getenv("LLM_BASE_URL", "").strip()

    if env_key and env_model:
        return {
            "current_model": env_model,
            "providers": [
                {
                    "id": "env_provider",
                    "name": f"环境模型 ({env_model})",
                    "base_url": env_base_url or "https://api.openai.com/v1",
                    "api_key": env_key,
                    "models": [env_model],
                    "is_custom": False,
                    "status": "connected"
                }
            ]
        }

    return {
        "current_model": "",
        "providers": []
    }

def save_models_config(cfg: Dict[str, Any]):
    """持久化保存模型与提供方配置 (严格写入用户中央数据目录，杜绝敏感配置污染源码仓库)"""
    try:
        USER_MODELS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_MODELS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存用户模型配置失败: {e}")

def get_active_models_list() -> List[str]:
    """仅返回已配置有效 API Key 的模型列表，彻底杜绝默认占位符与已删除幽灵模型"""
    cfg = load_models_config()
    active_models = []
    providers = cfg.get("providers", [])

    # 1. 优先从已配置并激活的提供方中提取模型
    for p in providers:
        raw_key = p.get("api_key", "").strip()
        if raw_key.startswith("${") and raw_key.endswith("}"):
            key = os.getenv(raw_key[2:-1], "").strip()
        elif raw_key.startswith("$"):
            key = os.getenv(raw_key[1:], "").strip()
        else:
            key = raw_key
        # 排除无效占位符
        if key and key not in ("your_api_key_here", "your_key", "sk-xxx", "sk-placeholder"):
            for m in p.get("models", []):
                if m and m not in active_models:
                    active_models.append(m)

    # 2. 仅在提供方列表为空时，才作为兜底读取环境变量，且必须为真实有效密钥
    if not active_models:
        env_key = os.getenv("LLM_API_KEY", "").strip()
        env_model = os.getenv("LLM_MODEL", "").strip()
        if env_key and env_model and env_key not in ("your_api_key_here", "your_key", "sk-xxx", "sk-placeholder"):
            active_models.append(env_model)

    return active_models

# ================= 辅助函数：跨项目历史扫描 =================
def scan_project_sessions(proj_dir: Path) -> List[Dict[str, Any]]:
    """扫描指定项目目录下的所有会话元数据（支持置顶与自定义重命名标题）"""
    sessions = []
    if not proj_dir.exists():
        return sessions

    pname = proj_dir.name
    pins = load_pins_config()
    pinned_sids = pins.get("pinned_sessions", {}).get(pname, [])
    custom_titles = pins.get("custom_titles", {}).get(pname, {})

    for f in proj_dir.glob("*.jsonl"):
        sid = f.stem
        if sid.endswith(".tmp"):
            continue

        # 0 字节文件属于未发生实际对话的空会话占位，静默清理并跳过，绝不在侧边栏展示
        try:
            if f.stat().st_size == 0:
                f.unlink()
                continue
        except Exception:
            pass

        turn_count = 0
        current_goal = ""
        mtime = f.stat().st_mtime

        try:
            with open(f, "r", encoding="utf-8", errors="replace") as jf:
                for line in jf:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        t = row.get("type")
                        if t == "turn_finished":
                            turn_count += 1
                            wm_goal = row.get("data", {}).get("working_memory", {}).get("current_goal", "")
                            if wm_goal and not current_goal:
                                current_goal = wm_goal[:28] + ("..." if len(wm_goal) > 28 else "")
                        elif t == "user_message" and not current_goal:
                            content = row.get("data", {}).get("content", "")
                            if content:
                                current_goal = content[:28] + ("..." if len(content) > 28 else "")
                    except Exception:
                        pass
        except Exception:
            pass

        # 友好相对时间计算
        diff_sec = time.time() - mtime
        if diff_sec < 3600:
            time_ago = "刚刚"
        elif diff_sec < 86400:
            time_ago = f"{int(diff_sec // 3600)}小时前"
        elif diff_sec < 86400 * 30:
            time_ago = f"{int(diff_sec // 86400)}天前"
        else:
            time_ago = "1个月"

        # 仅当会话包含实际对话轮次、用户提问或自定义标题时，才作为历史会话返回
        if turn_count == 0 and not current_goal and sid not in custom_titles and sid != "default":
            continue

        is_pinned = sid in pinned_sids
        display_title = custom_titles.get(sid) or current_goal or sid
        sessions.append({
            "session_id": sid,
            "turn_count": turn_count,
            "current_goal": display_title,
            "time_ago": time_ago,
            "is_active": sid == "default",
            "is_pinned": is_pinned,
            "mtime": mtime
        })

    # 置顶优先，其余按活跃时间倒序
    sessions.sort(key=lambda x: (1 if x.get("is_pinned") else 0, x["mtime"]), reverse=True)
    return sessions

def get_all_projects_metadata() -> List[Dict[str, Any]]:
    """扫描 history/ 目录，自动发现包含聊天历史的全部项目 (过滤已删除项目并严格绑定真实磁盘路径)"""
    projects = []
    known_lower = set()

    pins = load_pins_config()
    deleted_names = set(pins.get("deleted_projects", []))

    # 0. 清理已在删除黑名单中残留的磁盘物理空目录，确保磁盘目录与界面绝对一致
    if HISTORY_ROOT.exists():
        for d in list(HISTORY_ROOT.iterdir()):
            if d.is_dir() and d.name in deleted_names:
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

    # 1. 扫描 history/ 下的所有活跃项目目录
    if HISTORY_ROOT.exists():
        for d in HISTORY_ROOT.iterdir():
            if d.is_dir():
                pname = d.name
                if pname in deleted_names or pname.lower() in [dn.lower() for dn in deleted_names]:
                    continue
                if pname.lower() in ("_general", "workspace", "scratchpad", ".super-harness", ".super-harness", ".super_attachments", "super-server", "bin", "resources", "_internal"):
                    continue
                known_lower.add(pname.lower())
                proj_sessions = scan_project_sessions(d)
                
                # 全方位解析真实物理磁盘路径
                proj_path = str(resolve_project_workspace_root(pname))
                if proj_path and Path(proj_path).exists():
                    migrate_legacy_attachments(Path(proj_path))

                # 优先采用真实物理目录的标准大小写名称
                display_pname = pname
                if proj_path and Path(proj_path).exists() and Path(proj_path).name.lower() == pname.lower():
                    display_pname = Path(proj_path).name

                projects.append({
                    "name": display_pname,
                    "path": proj_path,
                    "session_count": len(proj_sessions),
                    "sessions": proj_sessions
                })

    # 2. 检查注册在 ~/.super-harness/projects.json 的磁盘工程 (双向一致同步：若 history/ 下已被物理删除，自动清理注册表绝不重新复活)
    extra_projects = get_registered_projects()
    registered_changed = False
    valid_registered = []
    for ep in extra_projects:
        ep_name = ep.get("name")
        ep_path = ep.get("path", "")
        if not ep_name:
            continue
        ep_name_lower = ep_name.lower()
        if ep_name in deleted_names or ep_name_lower in [dn.lower() for dn in deleted_names]:
            registered_changed = True
            continue
        ep_dir = HISTORY_ROOT / ep_name
        # 核心逻辑：若该项目在 history/ 下的物理目录不存在，判定为用户已在磁盘物理删除
        # 同步从 projects.json 和 pins_config 中剔除，绝不重新创建
        if not ep_dir.exists():
            registered_changed = True
            if ep_name not in deleted_names:
                pins.setdefault("deleted_projects", []).append(ep_name)
            pins["pinned_projects"] = [p for p in pins.get("pinned_projects", []) if p.lower() != ep_name_lower]
            pins["project_order"] = [p for p in pins.get("project_order", []) if p.lower() != ep_name_lower]
            if hasattr(bridge, "evict_project_agents"):
                bridge.evict_project_agents(ep_name)
            continue

        valid_registered.append(ep)

    if registered_changed:
        from server.project_utils import save_registered_projects
        save_registered_projects(valid_registered)
        save_pins_config(pins)

    # 3. 在源码开发模式下，仅当 HISTORY_ROOT / cur_name 实际存在时才列出，严禁强行插入已被删除的项目
    if not getattr(sys, "frozen", False):
        cur_name = default_workspace.root.name
        cur_dir = HISTORY_ROOT / cur_name
        if cur_name.lower() not in ("super-server", "bin", "resources", "_internal", "workspace", "super-harness", "super-harnes") and cur_name.lower() not in known_lower and cur_name not in deleted_names:
            if cur_dir.exists():
                cur_sessions = scan_project_sessions(cur_dir)
                projects.insert(0, {
                    "name": cur_name,
                    "path": str(default_workspace.root),
                    "session_count": len(cur_sessions),
                    "sessions": cur_sessions
                })

    pinned_projs = pins.get("pinned_projects", [])
    project_order = pins.get("project_order", [])
    for p in projects:
        p["is_pinned"] = p["name"] in pinned_projs

    def get_sort_key(item):
        pname = item.get("name", "")
        if pname in pinned_projs:
            return (0, pinned_projs.index(pname))
        if pname in project_order:
            return (1, project_order.index(pname))
        return (2, pname.lower())

    projects.sort(key=get_sort_key)
    return projects

def parse_project_turns_from_disk(project_name: str, session_id: str) -> Dict[str, Any]:
    """从 history/<project>/<session_id>.jsonl 直接读取还原轮次、工具与任务"""
    target_file = HISTORY_ROOT / project_name / f"{session_id}.jsonl"
    if not target_file.exists():
        return {
            "session_id": session_id,
            "project": project_name,
            "turns_count": 0,
            "turns": [],
            "all_actions": [],
            "tasks": [],
            "working_memory": {}
        }

    turns_map = {}
    all_actions = []
    working_memory_last = {}
    tool_results_by_turn = {}
    turn_start_times = {}
    turn_end_times = {}

    with open(target_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue

            tid = row.get("turn_id", 1)
            t = row.get("type")
            data = row.get("data", {})

            # 忽略所有非正整数轮次及控制/回滚事件，杜绝产生虚假的 turn-0
            if tid <= 0 or t in ("session_cleared", "session_reset", "turn_aborted", "rollback"):
                continue

            if tid not in turns_map:
                turns_map[tid] = {
                    "turn_id": tid,
                    "user_prompt": "",
                    "attachments": [],
                    "thought": "",
                    "assistant_response": "",
                    "actions": [],
                    "steps": []
                }
                tool_results_by_turn[tid] = {}

            if t == "tool_result":
                tc_id = data.get("tool_call_id")
                if tc_id:
                    tool_results_by_turn[tid][tc_id] = data.get("content", "")

            elif t == "user_message":
                turns_map[tid]["user_prompt"] = data.get("content", "")
                turns_map[tid]["attachments"] = data.get("attachments", [])
                if data.get("permission_mode"):
                    turns_map[tid]["permission_mode"] = data.get("permission_mode")
                turn_start_times[tid] = row.get("timestamp", time.time())

            elif t == "assistant_message":
                turn_end_times[tid] = max(turn_end_times.get(tid, 0), row.get("timestamp", time.time()))
                content = data.get("content", "")
                tcs = data.get("tool_calls", [])
                
                # 捕获思考内容与助理推理步骤 (对标需求 2: 独立捕获思考与正文，杜绝有思考时正文被 elif 吞掉)
                thought_cand = data.get("reasoning_content", "") or data.get("thought", "")
                if thought_cand:
                    if not turns_map[tid]["thought"]:
                        turns_map[tid]["thought"] = thought_cand
                    turns_map[tid]["steps"].append({
                        "id": f"th_{len(turns_map[tid]['steps'])}",
                        "type": "assistant",
                        "thought": thought_cand,
                        "timestamp": row.get("timestamp", time.time())
                    })

                if content and not tcs:
                    turns_map[tid]["assistant_response"] = content
                elif content and tcs:
                    if not turns_map[tid]["thought"]:
                        turns_map[tid]["thought"] = content
                    turns_map[tid]["steps"].append({
                        "id": f"th_{len(turns_map[tid]['steps'])}",
                        "type": "assistant",
                        "thought": content,
                        "timestamp": row.get("timestamp", time.time())
                    })

                for tc in tcs:
                    tc_id = tc.get("id")
                    func = tc.get("function", {})
                    fname = func.get("name", "")
                    raw_args = func.get("arguments", "")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {"raw": raw_args}
                    meta = format_tool_display(fname, args)
                    
                    out_content = tool_results_by_turn[tid].get(tc_id, "")
                    is_err = any(k in out_content for k in ["【安全拦截拒绝】", "【执行状态: 退出码 1】", "Error:", "执行失败:"])

                    act_item = {
                        "id": tc_id or f"act_{len(all_actions)}",
                        "tool": fname,
                        "display": meta["display"],
                        "desc": meta["desc"],
                        "path": meta["path"],
                        "args": args,
                        "status": "error" if is_err else "success",
                        "output": out_content,
                        "elapsed": 0.15,
                        "timestamp": row.get("timestamp", time.time())
                    }
                    turns_map[tid]["actions"].append(act_item)
                    all_actions.append(act_item)

                    turns_map[tid]["steps"].append({
                        "id": tc_id or f"step_{len(turns_map[tid]['steps'])}",
                        "type": "tool",
                        "tool": fname,
                        "display": meta["display"],
                        "desc": meta["desc"],
                        "path": meta["path"],
                        "args": args,
                        "status": "error" if is_err else "success",
                        "output": out_content,
                        "elapsed": 0.15,
                        "timestamp": row.get("timestamp", time.time())
                    })

            elif t in ("turn_finished", "turn_aborted"):
                turn_end_times[tid] = max(turn_end_times.get(tid, 0), row.get("timestamp", time.time()))
                wm = data.get("working_memory", {})
                working_memory_last = wm
                if wm.get("current_goal") and not turns_map[tid]["user_prompt"]:
                    turns_map[tid]["user_prompt"] = wm.get("current_goal")

    # 计算并写入该轮真实的发送至回答完成时间
    file_mtime = target_file.stat().st_mtime if target_file.exists() else 0
    for tid, tdata in turns_map.items():
        t_start = turn_start_times.get(tid)
        t_end = turn_end_times.get(tid)
        if t_start and t_end and t_end >= t_start:
            tdata["elapsed"] = round(max(1.0, t_end - t_start), 1)
        elif not tdata.get("elapsed"):
            tdata["elapsed"] = 1.0
        # 严格使用历史持久化时间戳；若均无则以历史文件物理修改时间 mtime 兜底，绝不使用当前重启时间
        tdata["timestamp"] = t_end or t_start or file_mtime
        tdata["start_timestamp"] = t_start or tdata["timestamp"]

    # 填充缺失工具的输出
    for tid, tdata in turns_map.items():
        res_map = tool_results_by_turn.get(tid, {})
        for act in tdata["actions"]:
            if not act["output"] and act["id"] in res_map:
                act["output"] = res_map[act["id"]]
        for st in tdata.get("steps", []):
            if st.get("type") == "tool" and not st.get("output") and st.get("id") in res_map:
                st["output"] = res_map[st["id"]]

    sorted_turns = [
        turns_map[k] for k in sorted(turns_map.keys())
        if k > 0 and (
            turns_map[k]["user_prompt"] or 
            turns_map[k]["assistant_response"] or 
            turns_map[k]["thought"] or 
            turns_map[k]["actions"] or 
            turns_map[k].get("steps")
        )
    ]

    # 若首个轮次提问因历史压缩等原因缺失，且工作记忆中有明确当前目标，自动补全首轮提问
    if sorted_turns and not sorted_turns[0]["user_prompt"] and working_memory_last.get("current_goal"):
        sorted_turns[0]["user_prompt"] = working_memory_last.get("current_goal")

    # 构建工作记忆任务列表
    tasks = []
    if working_memory_last:
        for f in working_memory_last.get("inspected_files", {}).keys():
            tasks.append({"id": f"t_{len(tasks)}", "title": f"走查: {f}", "completed": True})
        for f in working_memory_last.get("modified_files", []):
            tasks.append({"id": f"t_{len(tasks)}", "title": f"改动: {f}", "completed": True})
        if working_memory_last.get("current_goal"):
            tasks.append({"id": f"t_{len(tasks)}", "title": f"目标: {working_memory_last.get('current_goal')}", "completed": True})

    all_steps = []
    for t in sorted_turns:
        for st in t.get("steps", []):
            all_steps.append(st)

    return {
        "session_id": session_id,
        "project": project_name,
        "turns_count": len(sorted_turns),
        "turns": sorted_turns,
        "all_actions": all_actions,
        "all_steps": all_steps,
        "tasks": tasks,
        "working_memory": working_memory_last
    }

# ================= 核心接口实现 =================

@app.get("/api/status")
def get_status():
    """获取当前智能体与工作区系统状态"""
    status = bridge.get_status()
    cfg = load_models_config()
    status["model"] = cfg.get("current_model", status.get("model"))
    status["permission_mode"] = getattr(default_policy, "mode", "auto")
    return status

@app.get("/api/mode")
def get_mode():
    """获取当前安全审批模式 (AUTO 模式与 ASK 模式)"""
    cur_mode = getattr(default_policy, "mode", "auto")
    return {
        "current_mode": cur_mode,
        "modes": [
            {
                "id": "auto",
                "name": "AUTO 模式",
                "desc": "全自动免打扰执行，非黑名单高危命令自动放行（默认推荐）"
            },
            {
                "id": "ask",
                "name": "ASK 人工审批",
                "desc": "敏感命令每次弹窗确认后执行"
            }
        ]
    }

@app.post("/api/mode")
def switch_mode(req: ModeSwitchRequest):
    """切换安全模式"""
    if req.mode in ("auto", "ask"):
        default_policy.mode = req.mode
        return {"success": True, "mode": req.mode}
    raise HTTPException(status_code=400, detail="不支持的模式，仅支持 auto 与 ask")

@app.get("/api/models")
def get_available_models():
    """获取所有已配置有效的大模型列表及对应的提供方映射（未配置时返回空列表与空字符串）"""
    cfg = load_models_config()
    active_models = get_active_models_list()
    cur = cfg.get("current_model", "")
    if cur not in active_models:
        cur = active_models[0] if active_models else ""

    # 构建 model -> provider_name 映射表供前端下拉菜单标注来源
    model_providers = {}
    for p in cfg.get("providers", []):
        p_name = p.get("name", "自定义")
        for m in p.get("models", []):
            if m:
                model_providers[m] = p_name

    return {
        "current_model": cur,
        "models": active_models,
        "model_providers": model_providers
    }

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

class ModelTestRequest(BaseModel):
    base_url: str
    api_key: str
    model: Optional[str] = None
    protocol: Optional[str] = "openai_chat" 

@app.post("/api/models/test")
def test_provider_connection(req: ModelTestRequest):
    """测试模型提供方连通性与 API Key 有效性"""
    url = clean_base_url(req.base_url, getattr(req, "protocol", "openai_chat") or "openai_chat")
    key = req.api_key.strip()
    if not url or not key:
        raise HTTPException(status_code=400, detail="接口地址与 API 密钥不能为空")

    try:
        from openai import OpenAI
        test_client = OpenAI(api_key=key, base_url=url, timeout=12.0)
        test_model = (req.model or "").strip() or "deepseek-chat"
        try:
            test_client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=3
            )
            return {"success": True, "message": f"连接成功！模型「{test_model}」调用正常响应。"}
        except Exception as e_chat:
            err_str = str(e_chat)
            if "model" in err_str.lower() or "not found" in err_str.lower() or "404" in err_str:
                try:
                    m_list = test_client.models.list()
                    available_names = [getattr(m, "id", str(m)) for m in getattr(m_list, "data", [])][:4]
                    avail_hint = f"（检测到可用模型: {", ".join(available_names)}）" if available_names else ""
                    return {"success": False, "error": f"API Key 鉴权通过，但模型「{test_model}」在服务端不存在 (404 Not Found)。{avail_hint} 请核对映射模型名称。"}
                except Exception:
                    return {"success": False, "error": f"调用失败 (404 Not Found): 请核对 Base URL 路径是否正确，以及模型名称「{test_model}」是否在该平台存在。"}
            raise e_chat
    except Exception as e:
        logger.warning(f"Model test connection failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/models/switch")
def switch_model(req: ModelSwitchRequest):
    """切换当前智能体使用的大模型"""
    cfg = load_models_config()
    cfg["current_model"] = req.model
    save_models_config(cfg)

    if bridge.agent:
        bridge.agent.model = req.model
    if hasattr(bridge, "reload_agents_config"):
        bridge.reload_agents_config()
    return {"success": True, "current_model": req.model}

@app.get("/api/models/providers")
def get_providers():
    """获取所有模型提供方（本地桌面模式返回明文密钥以供回显编辑，同时保留脱敏字段）"""
    cfg = load_models_config()
    providers_list = []
    for p in cfg.get("providers", []):
        key = p.get("api_key", "")
        masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("已配置" if key else "")
        status = "connected" if key or p.get("status") == "connected" else "unconfigured"
        providers_list.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "base_url": p.get("base_url"),
            "api_key": key,
            "api_key_masked": masked_key,
            "models": p.get("models", []),
            "is_custom": p.get("is_custom", True),
            "protocol": p.get("protocol", "openai_chat"),
            "status": status
        })
    return {"providers": providers_list}

@app.post("/api/models/providers")
def save_provider(req: ProviderConfigRequest):
    """添加或编辑模型提供方（新增自定义模型后自动映射到对话切换栏）"""
    cfg = load_models_config()
    providers = cfg.get("providers", [])
    
    pid = req.id or f"provider_{int(time.time())}"
    found = False
    clean_url = clean_base_url(req.base_url, getattr(req, "protocol", "openai_chat") or "openai_chat")

    for idx, p in enumerate(providers):
        if p.get("id") == pid or p.get("name") == req.name:
            providers[idx] = {
                "id": pid,
                "name": req.name,
                "base_url": clean_url,
                "api_key": req.api_key or p.get("api_key", ""),
                "models": req.models,
                "is_custom": req.is_custom,
                "protocol": getattr(req, "protocol", "openai_chat") or "openai_chat",
                "status": "connected" if req.api_key or p.get("api_key") else "unconfigured"
            }
            found = True
            break

    if not found:
        providers.append({
            "id": pid,
            "name": req.name,
            "base_url": clean_url,
            "api_key": req.api_key,
            "models": req.models,
            "is_custom": req.is_custom,
            "protocol": getattr(req, "protocol", "openai_chat") or "openai_chat",
            "status": "connected" if req.api_key else "unconfigured"
        })

    cfg["providers"] = providers
    save_models_config(cfg)
    if hasattr(bridge, "reload_agents_config"):
        bridge.reload_agents_config()
    return {"success": True, "providers": providers, "active_models": get_active_models_list()}

@app.delete("/api/models/providers/{provider_id}")
def delete_provider(provider_id: str):
    """删除自定义提供方"""
    cfg = load_models_config()
    cfg["providers"] = [p for p in cfg.get("providers", []) if p.get("id") != provider_id]
    save_models_config(cfg)
    if hasattr(bridge, "reload_agents_config"):
        bridge.reload_agents_config()
    return {"success": True, "active_models": get_active_models_list()}

def get_recent_sessions() -> List[Dict[str, Any]]:
    """扫描 history/_general 目录，获取未绑定具体工程的独立/最近会话列表"""
    gen_dir = HISTORY_ROOT / "_general"
    if not gen_dir.exists():
        return []
    return scan_project_sessions(gen_dir)

@app.get("/api/workspaces")
def get_workspaces():
    """获取所有已扫描到的项目工作区列表以及最近独立会话列表"""
    all_projects = get_all_projects_metadata()
    recent_sessions = get_recent_sessions()
    active_name = default_workspace.root.name
    if active_name.lower() in ("super-server", "bin", "resources", "_internal", "workspace", "scratchpad", "_general") or not any(p["name"] == active_name for p in all_projects):
        if all_projects:
            active_name = all_projects[0]["name"]
        else:
            active_name = ""

    current_root = str(default_workspace.root) if active_name else ""
    return {
        "current": current_root,
        "name": active_name,
        "projects": all_projects,
        "recent_sessions": recent_sessions
    }

@app.post("/api/workspaces/switch")
def switch_workspace(req: WorkspaceSwitchRequest):
    """切换工作区根目录或目标项目"""
    target_path = req.path
    if not target_path and req.name:
        # 寻找已知项目的路径
        all_projs = get_all_projects_metadata()
        for p in all_projs:
            if p["name"] == req.name and p["path"] and Path(p["path"]).exists():
                target_path = p["path"]
                break
        
        if not target_path:
            # 切换项目会话目录名称
            if bridge.agent:
                bridge.agent.session_manager.project_name = req.name
                bridge.agent.session_manager.history_dir = HISTORY_ROOT / req.name
                bridge.agent.session_manager.history_dir.mkdir(parents=True, exist_ok=True)
            return {"success": True, "name": req.name, "workspace_path": str(default_workspace.root)}

    try:
        new_root = Path(target_path).resolve()
        default_workspace.set_root(new_root)
        if bridge.agent:
            bridge.agent.switch_workspace(target_path)
        migrate_legacy_attachments(new_root)
        return {"success": True, "workspace_path": str(new_root), "name": new_root.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/workspaces/add")
def add_workspace(req: WorkspaceAddRequest):
    """选择磁盘项目并注册为新工作区 (支持用户自定义工作区名称与路径绑定)"""
    p = Path(req.path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail="指定的磁盘目录不存在或不是文件夹")

    proj_name = (req.name or p.name).strip()
    norm_path = str(p)

    # 1. 注册到 ~/.super-harness/projects.json
    register_project_path(proj_name, norm_path)

    # 2. 自动创建对应项目的历史目录并持久化 project_state.json
    target_hist = HISTORY_ROOT / proj_name
    target_hist.mkdir(parents=True, exist_ok=True)
    ps_file = target_hist / "project_state.json"
    ps_data = {"project_name": proj_name, "workspace_root": norm_path}
    with open(ps_file, "w", encoding="utf-8") as f:
        json.dump(ps_data, f, ensure_ascii=False, indent=2)

    # 3. 若此前在已删除列表中，解除删除标记
    # 3. 若之前在删除列表中，解除删除标记，并维护稳定的 project_order
    pins = load_pins_config()
    deleted_list = pins.get("deleted_projects", [])
    if any(x.lower() == proj_name.lower() for x in deleted_list):
        pins["deleted_projects"] = [x for x in deleted_list if x.lower() != proj_name.lower()]
    p_order = pins.setdefault("project_order", [])
    if proj_name not in p_order and not any(x.lower() == proj_name.lower() for x in p_order):
        p_order.append(proj_name)
    save_pins_config(pins)

    # 4. 动态切换工作区
    set_workspace_root(norm_path)
    if bridge.agent:
        bridge.agent.switch_workspace(norm_path)
    migrate_legacy_attachments(p)

    return {
        "success": True,
        "name": proj_name,
        "path": norm_path,
        "projects": get_all_projects_metadata()
    }

@app.get("/api/sessions")
def get_sessions(project: Optional[str] = Query(None)):
    """获取指定项目（或当前项目）下的所有真实会话列表"""
    proj_name = project or default_workspace.root.name
    proj_dir = HISTORY_ROOT / proj_name

    sessions = scan_project_sessions(proj_dir)
    active_sid = "default"
    if sessions:
        active_sid = sessions[0]["session_id"]

    return {
        "project": proj_name,
        "active_session_id": active_sid,
        "sessions": sessions
    }

@app.get("/api/sessions/turns")
def get_session_turns(session_id: Optional[str] = None, project: Optional[str] = None):
    """读取并解析指定项目与会话的全部真实轮次、工具调用链与输出结果"""
    proj_name = project or default_workspace.root.name
    sid = session_id or "default"

    # 直接从磁盘历史精准读取
    result = parse_project_turns_from_disk(proj_name, sid)
    return result

class SessionMoveRequest(BaseModel):
    session_id: str
    from_project: str = "_general"
    to_project: str

@app.post("/api/sessions/move")
def move_session(req: SessionMoveRequest):
    """将会话从最近自由对话移入指定项目工作区"""
    src_file = HISTORY_ROOT / (req.from_project or "_general") / f"{req.session_id}.jsonl"
    if not src_file.exists():
        raise HTTPException(status_code=404, detail="源会话历史文件不存在")
    dst_dir = HISTORY_ROOT / req.to_project
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / f"{req.session_id}.jsonl"
    shutil.move(str(src_file), str(dst_file))
    return {"success": True, "session_id": req.session_id, "project": req.to_project}

@app.post("/api/sessions/create")
def create_session(req: Optional[SessionActionRequest] = None):
    """创建全新会话 (支持项目会话或最近自由独立会话)"""
    raw_p = (req.project or "").strip() if req else ""
    proj_name = raw_p if raw_p else ("_general" if not default_workspace.root.name or default_workspace.root.name.lower() in ("workspace", "scratchpad") else default_workspace.root.name)
    sid = req.session_id if req and req.session_id else f"session_{int(time.time()*1000)}"
    
    # 仅确保磁盘目录存在，未产生实际对话前绝不在磁盘触碰 0 字节文件
    proj_dir = HISTORY_ROOT / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    if bridge.agent and proj_name == default_workspace.root.name:
        bridge.agent.create_session(sid)

    return {"success": True, "session_id": sid, "project": proj_name}

@app.delete("/api/sessions/delete")
@app.post("/api/sessions/delete")
def delete_session(
    req: Optional[SessionActionRequest] = None,
    session_id: Optional[str] = Query(None),
    project: Optional[str] = Query(None)
):
    """删除会话 (物理清除磁盘文件、同步剔除内存缓存与图钉状态，支持 DELETE 与 POST，支持 body 与 query 参数)"""
    sid = (req.session_id if req and req.session_id else session_id)
    if not sid:
        raise HTTPException(status_code=400, detail="session_id 不能为空")

    raw_proj = (req.project if req and req.project else project)
    proj_name = raw_proj or default_workspace.root.name

    # 1. 物理删除 history 目录下的 jsonl 文件 (兼顾大小写匹配)
    target_dir = HISTORY_ROOT / proj_name
    if not target_dir.exists() and HISTORY_ROOT.exists():
        for d in HISTORY_ROOT.iterdir():
            if d.is_dir() and d.name.lower() == proj_name.lower():
                target_dir = d
                break

    target_file = target_dir / f"{sid}.jsonl"
    deleted_file = False
    if target_file.exists():
        try:
            target_file.unlink()
            deleted_file = True
        except Exception as e:
            logger.warning(f"删除会话历史文件失败: {e}")

    # 兜底全盘扫描：若按目标工程未找到文件，在 HISTORY_ROOT 的所有子目录及根目录搜索并物理删除
    if not deleted_file and HISTORY_ROOT.exists():
        for pd in HISTORY_ROOT.iterdir():
            if pd.is_dir():
                candidate = pd / f"{sid}.jsonl"
                if candidate.exists():
                    try:
                        candidate.unlink()
                        deleted_file = True
                        logger.info(f"在项目目录 {pd.name} 中找到并删除了会话文件 {sid}.jsonl")
                    except Exception as e:
                        logger.warning(f"删除会话历史文件失败: {e}")
                    break

    # 2. 同步清理内存 agent 对象
    if hasattr(bridge, "evict_session_agent"):
        bridge.evict_session_agent(proj_name, sid)

    # 3. 同步清理置顶与自定义标题
    try:
        pins = load_pins_config()
        changed = False
        pinned_sids = pins.get("pinned_sessions", {}).get(proj_name, [])
        if sid in pinned_sids:
            pins["pinned_sessions"][proj_name] = [s for s in pinned_sids if s != sid]
            changed = True
        custom_titles = pins.get("custom_titles", {}).get(proj_name, {})
        if sid in custom_titles:
            custom_titles.pop(sid, None)
            changed = True
        if changed:
            save_pins_config(pins)
    except Exception as e:
        logger.warning(f"清理图钉配置失败: {e}")

    # 4. 同步清理此会话绑定的本地上传附件
    try:
        ws_root = resolve_project_workspace_root(proj_name) if raw_proj else default_workspace.root
        if ws_root:
            att_dir = ws_root / ".super-harness" / "attachments" / sid
            if att_dir.exists():
                shutil.rmtree(att_dir, ignore_errors=True)
            old_att_dir = ws_root / ".super_attachments" / sid
            if old_att_dir.exists():
                shutil.rmtree(old_att_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"清理会话附件失败: {e}")
    return {"success": True, "session_id": sid, "project": proj_name}

@app.get("/api/skills")
def get_skills():
    """获取挂载的专家技能 SOP 清单（附带所在磁盘路径与作用域说明）"""
    skills = default_skill_manager.list_skills()
    return {
        "skills": [
            {
                "name": getattr(s, "name", str(s)),
                "description": getattr(s, "description", ""),
                "source_scope": getattr(s, "source_scope", "workspace"),
                "directory": str(getattr(s, "directory", ""))
            }
            for s in skills
        ]
    }

@app.get("/api/builtin_tools")
def get_builtin_tools():
    """获取系统内置核心工具清单 (含原 MCP 迁入的计算与系统时间工具)"""
    builtin_catalog = [
        {
            "id": "calculate",
            "name": "calculate (精确数学计算)",
            "category": "系统计算",
            "description": "原外部 MCP 迁入核心内置，提供加减乘除、求余、幂运算与括号优先级的零延迟高精度数学运算。",
            "read_only": True
        },
        {
            "id": "get_current_time",
            "name": "get_current_time (实时系统时间)",
            "category": "环境感知",
            "description": "原外部 MCP 迁入核心内置，即时获取宿主机操作系统的年月日、时分秒精准时间与星期。",
            "read_only": True
        },
        {
            "id": "get_system_info",
            "name": "get_system_info (宿主机系统探针)",
            "category": "环境感知",
            "description": "原外部 MCP 迁入核心内置，实时感知操作系统内核版本、平台架构与 Python 解释器运行时。",
            "read_only": True
        },
        {
            "id": "read_file",
            "name": "read_file (文件分段查阅)",
            "category": "文件与代码",
            "description": "内置安全分段读取工程文本或代码，带行号标注与超大文件窗口防溢出保护。",
            "read_only": True
        },
        {
            "id": "write_file",
            "name": "write_file (安全物理覆写)",
            "category": "文件与代码",
            "description": "写前自动创建物理快照备份，原子安全刷盘写入新文件或覆盖现有文件。",
            "read_only": False
        },
        {
            "id": "apply_patch",
            "name": "apply_patch (精准代码补丁)",
            "category": "文件与代码",
            "description": "工业级 Unified Diff 增量补丁应用器，带严格跨工作区防篡改安全沙箱。",
            "read_only": False
        },
        {
            "id": "view_file_outline",
            "name": "view_file_outline (语法大纲抽取)",
            "category": "代码索引",
            "description": "基于 AST 语法树快速提取类、函数定义与接口签名，毫秒级梳理架构拓扑。",
            "read_only": True
        },
        {
            "id": "grep_text",
            "name": "grep_text (全局正则检索)",
            "category": "代码索引",
            "description": "多线程高速检索工程内的关键词、函数调用或正则表达式，支持目录剪枝过滤。",
            "read_only": True
        },
        {
            "id": "run_shell",
            "name": "run_shell (受控终端执行)",
            "category": "终端运行",
            "description": "在目标工作区隔离执行 Shell 命令，内置破坏性命令拦截与 ASK 模式审批。",
            "read_only": False
        },
        {
            "id": "ask_user",
            "name": "ask_user / request_user_input",
            "category": "交互决策",
            "description": "在思考执行链中发起交互决策，向用户推送选择题或自定义输入卡片。",
            "read_only": True
        }
    ]
    return {"tools": builtin_catalog}

@app.get("/api/mcp")
def get_mcp():
    """获取外部 MCP 扩展服务状态（包含服务标识、绑定脚本与工具清单）"""
    mcp_meta = {
        "weather": {
            "name": "weather (外部天气气象服务)",
            "desc": "由原脚本重构为标准独立外部 MCP 服务，通过 wttr.in 开放接口获取指定城市的实时天气与气象指标。",
            "script": "mcp/servers/weather_server.py",
            "tools": ["mcp__weather__get_weather"]
        }
    }

    all_tools = bridge.agent.executor.registry.get_tool_names() if bridge.agent else []
    mcp_tools = [t for t in all_tools if t.startswith("mcp__")]
    clients = list(bridge.agent.mcp_manager.clients.keys()) if bridge.agent else []
    servers_detail = []

    configs = getattr(bridge.agent.mcp_manager, "configs", {}) if bridge.agent else {}
    for sid, cfg in configs.items():
        meta = mcp_meta.get(sid, {
            "name": f"{sid} (外部 MCP 扩展)",
            "desc": "独立子进程运行的外部 MCP 协议服务。",
            "script": " ".join(cfg.args) if cfg.args else cfg.command,
            "tools": []
        })
        tools_for_srv = [t for t in mcp_tools if f"mcp__{sid}__" in t or sid in t]
        servers_detail.append({
            "server_id": sid,
            "name": meta["name"],
            "description": meta["desc"],
            "script": meta["script"],
            "command": cfg.command,
            "args": cfg.args,
            "trust_level": cfg.trust_level,
            "status": "connected",
            "tools": tools_for_srv or meta["tools"]
        })

    # 若未初始化完成，提供默认已注册的 weather 详情
    if not servers_detail:
        for sid, meta in mcp_meta.items():
            servers_detail.append({
                "server_id": sid,
                "name": meta["name"],
                "description": meta["desc"],
                "script": meta["script"],
                "command": "python",
                "args": [meta["script"]],
                "trust_level": "trusted",
                "status": "connected",
                "tools": meta["tools"]
            })

    return {
        "clients": clients or list(mcp_meta.keys()),
        "tools": mcp_tools,
        "servers_detail": servers_detail
    }

@app.get("/api/file/read")
def read_file_content(path: str = Query(...)):
    """读取指定代码文件内容"""
    try:
        resolved_path = default_workspace.resolve_path(path)
        if not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
        ext = resolved_path.suffix.lstrip(".")
        return {
            "path": str(resolved_path),
            "filename": resolved_path.name,
            "extension": ext,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/attachments/upload")
async def upload_attachments(
    files: List[UploadFile] = File(...),
    project: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """上传文档、图片与数据附件并返回保存路径及预览信息"""
    proj_name = project or default_workspace.root.name
    ws_root = resolve_project_workspace_root(project) if project else default_workspace.root
    migrate_legacy_attachments(ws_root)
    sid = session_id or "default"
    save_dir = ws_root / ".super-harness" / "attachments" / sid
    save_dir.mkdir(parents=True, exist_ok=True)

    uploaded_items = []
    for f in files:
        clean_name = Path(f.filename).name
        target_path = save_dir / clean_name
        if target_path.exists():
            base = target_path.stem
            ext = target_path.suffix
            target_path = save_dir / f"{base}_{int(time.time()*1000)}{ext}"

        content = await f.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"文件 {clean_name} 超过 50MB 大小限制，建议上传轻量级文档或图片")
        target_path.write_bytes(content)

        ftype = detect_attachment_type(clean_name)
        resolved_path = str(target_path.resolve())
        uploaded_items.append({
            "id": f"att_{int(time.time()*1000)}_{len(uploaded_items)}",
            "name": clean_name,
            "size": len(content),
            "type": ftype,
            "path": resolved_path,
            "url": f"http://127.0.0.1:8765/api/attachments/raw?path={urllib.parse.quote(resolved_path)}"
        })

    return {"attachments": uploaded_items}

@app.get("/api/attachments/raw")
def get_attachment_raw(path: str):
    """直接读取本地附件二进制流 (用于图片渲染或文档下载)"""
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="附件不存在")
    return FileResponse(path=str(target), filename=target.name)

@app.post("/api/approval")
def resolve_approval_api(req: ApprovalResponseModel):
    ok = bridge.resolve_approval(req.ticket_id, approved=req.approved, trust_session=req.trust_session or False)
    return {"success": ok}

@app.post("/api/user_input")
def resolve_user_input_api(req: UserInputResponseModel):
    ok = bridge.resolve_user_input(req.request_id, selected_option=req.selected_option or "", custom_input=req.custom_input or "")
    return {"success": ok}

@app.post("/api/permission_mode")
def set_permission_mode_api(req: PermissionModeModel):
    new_mode = default_policy.normalize_mode(req.mode)
    default_policy.mode = new_mode
    if new_mode in ("auto", "edit_auto"):
        bridge.unblock_all_pending_approvals(approved=True)
    return {"success": True, "mode": default_policy.mode}


class TerminalExecRequest(BaseModel):
    command: str
    cwd: Optional[str] = None

@app.post("/api/terminal/exec")
def terminal_exec_api(req: TerminalExecRequest):
    target_cwd = req.cwd or str(default_workspace.root)
    try:
        res = subprocess.run(
            req.command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "【命令执行超时 (60s)】", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 1}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """全双工实时通信：接收 Prompt 并向前端持续广播工具流与执行结果"""
    await websocket.accept()
    loop = asyncio.get_running_loop()
    active_tasks: Dict[str, asyncio.Task] = {}
    turn_start_times: Dict[str, float] = {}
    aborted_session_keys: Set[str] = set()

    try:
        status = bridge.get_status()
        await websocket.send_json({"event": "connected", "status": status})

        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                continue

            msg_type = payload.get("type", "prompt")

            if msg_type == "prompt":
                prompt_text = payload.get("prompt", "").strip()
                attachments = payload.get("attachments", [])
                if not prompt_text and not attachments:
                    continue

                model = payload.get("model")
                perm_mode = payload.get("permission_mode", "auto")
                session_id = payload.get("session_id", "default")
                project_name = payload.get("project_name", default_workspace.root.name)
                session_key = f"{project_name}:{session_id}"

                await websocket.send_json({
                    "event": "prompt_received",
                    "prompt": prompt_text,
                    "attachments": attachments,
                    "session_id": session_id,
                    "project": project_name,
                    "timestamp": asyncio.get_event_loop().time()
                })

                # 若当前会话已有正在运行的未完成任务，先行安全中断并注销旧任务 (对标需求 5)
                if session_key in active_tasks and not active_tasks[session_key].done():
                    bridge.abort_session(session_id, project_name)
                    active_tasks[session_key].cancel()

                turn_start_times[session_key] = time.time()
                aborted_session_keys.discard(session_key)

                def emit_event(ev: Dict[str, Any]):
                    if session_key in aborted_session_keys:
                        return
                    ev.setdefault("session_id", session_id)
                    ev.setdefault("project", project_name)
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json(ev),
                        loop
                    )

                async def run_prompt_task(s_key=session_key, s_id=session_id, p_name=project_name, p_text=prompt_text, m=model, pm=perm_mode, atts=attachments):
                    try:
                        await bridge.execute_prompt_stream(
                            prompt=p_text,
                            event_callback=emit_event,
                            model=m,
                            permission_mode=pm,
                            session_id=s_id,
                            project_name=p_name,
                            attachments=atts
                        )
                    except asyncio.CancelledError:
                        logger.info(f"Prompt task cancelled for session {s_key}")
                    except Exception as err:
                        try:
                            await websocket.send_json({
                                "event": "error",
                                "session_id": s_id,
                                "project": p_name,
                                "message": str(err)
                            })
                        except Exception:
                            pass
                    finally:
                        if s_key in active_tasks and active_tasks[s_key] == asyncio.current_task():
                            active_tasks.pop(s_key, None)

                task = asyncio.create_task(run_prompt_task())
                active_tasks[session_key] = task

            elif msg_type == "set_permission_mode":
                perm_mode = payload.get("permission_mode", "auto")
                new_mode = default_policy.normalize_mode(perm_mode)
                default_policy.mode = new_mode
                if new_mode in ("auto", "edit_auto"):
                    bridge.unblock_all_pending_approvals(approved=True)
                logger.info(f"WebSocket updated permission mode: {default_policy.mode}")
                await websocket.send_json({
                    "event": "permission_mode_updated",
                    "mode": default_policy.mode,
                    "session_id": payload.get("session_id", "default"),
                    "project": payload.get("project_name", "")
                })

            elif msg_type == "approval_response":
                ticket_id = payload.get("ticket_id")
                approved = payload.get("approved", False)
                trust = payload.get("trust_session", False)
                ok = bridge.resolve_approval(ticket_id, approved=approved, trust_session=trust)
                logger.info(f"WebSocket handled approval response: ticket={ticket_id}, approved={approved}, trust={trust}, resolved={ok}")

            elif msg_type == "user_input_response":
                req_id = payload.get("request_id")
                sel = payload.get("selected_option", "")
                cust = payload.get("custom_input", "")
                sid = payload.get("session_id", "default")
                pname = payload.get("project_name", "")
                # 动态自适应响应方案审批决策：若用户在循环内批准了方案，自动切换策略模式并放行写操作
                if "auto" in sel.lower() or "批准" in sel:
                    default_policy.mode = "auto"
                    default_policy.session_approved = True
                    logger.info("Plan mode approved by user; auto switched policy mode to 'auto'")
                    await websocket.send_json({
                        "event": "permission_mode_updated",
                        "mode": "auto",
                        "session_id": sid,
                        "project": pname
                    })
                elif "edit" in sel.lower():
                    default_policy.mode = "edit_auto"
                    default_policy.session_approved = True
                    logger.info("Plan mode approved by user; auto switched policy mode to 'edit_auto'")
                    await websocket.send_json({
                        "event": "permission_mode_updated",
                        "mode": "edit_auto",
                        "session_id": sid,
                        "project": pname
                    })
                ok = bridge.resolve_user_input(req_id, selected_option=sel, custom_input=cust)
                logger.info(f"WebSocket handled user input response: req_id={req_id}, selected='{sel}', resolved={ok}")

            elif msg_type == "abort":
                session_id = payload.get("session_id", "default")
                project_name = payload.get("project_name", default_workspace.root.name)
                session_key = f"{project_name}:{session_id}"

                # 标记该会话已中止，立即静音所有来自后台执行线程的在途事件广播
                aborted_session_keys.add(session_key)

                # 立即向底层 agent 派发中止信号，并取消异步任务 (对标需求 5)
                bridge.abort_session(session_id, project_name)
                if session_key in active_tasks and not active_tasks[session_key].done():
                    active_tasks[session_key].cancel()
                    active_tasks.pop(session_key, None)

                # 计算从用户发送到暂停的真实总耗时
                t_start = turn_start_times.get(session_key, time.time())
                elapsed = round(max(1.0, time.time() - t_start), 1)

                await websocket.send_json({
                    "event": "assistant_response",
                    "content": "【用户已手动暂停】已终止当前思考与工具调用。",
                    "elapsed": elapsed,
                    "session_id": session_id,
                    "project": project_name,
                    "timestamp": asyncio.get_event_loop().time()
                })

            elif msg_type == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        for t in list(active_tasks.values()):
            if not t.done():
                t.cancel()


class WorkspaceEditRequest(BaseModel):
    old_name: str
    new_name: str
    path: Optional[str] = None

class WorkspacePinRequest(BaseModel):
    name: str
    pinned: bool

class WorkspaceDeleteRequest(BaseModel):
    name: str

class SessionRenameRequest(BaseModel):
    project: str
    session_id: str
    new_title: str

class SessionPinRequest(BaseModel):
    project: str
    session_id: str
    pinned: bool

class SessionClearRequest(BaseModel):
    project: str
    session_id: str

PINS_FILE = HISTORY_ROOT / "pins_config.json"

def load_pins_config() -> Dict[str, Any]:
    if PINS_FILE.exists():
        try:
            with open(PINS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pinned_projects": [], "project_order": [], "deleted_projects": [], "pinned_sessions": {}, "custom_titles": {}}

def save_pins_config(data: Dict[str, Any]):
    PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PINS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.post("/api/workspaces/edit")
def edit_workspace(req: WorkspaceEditRequest):
    """编辑工作区名称与磁盘路径"""
    pins = load_pins_config()
    old_p = HISTORY_ROOT / req.old_name
    new_p = HISTORY_ROOT / req.new_name

    # 1. 重命名 history 目录
    if req.old_name != req.new_name and old_p.exists():
        try:
            if new_p.exists():
                shutil.rmtree(new_p)
            old_p.rename(new_p)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重命名历史目录失败: {e}")

    # 2. 更新已登记工作区 projects.json
    proj_map_file = Path.home() / ".super-harness" / "projects.json"
    if proj_map_file.exists():
        try:
            with open(proj_map_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
            updated = False
            for p in projects:
                if p.get("name") == req.old_name:
                    p["name"] = req.new_name
                    if req.path:
                        p["path"] = str(Path(req.path).resolve())
                    updated = True
                    break
            if updated:
                with open(proj_map_file, "w", encoding="utf-8") as f:
                    json.dump(projects, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 3. 更新 project_state.json 中的 workspace_root
    target_history = new_p if new_p.exists() else (HISTORY_ROOT / req.new_name)
    target_history.mkdir(parents=True, exist_ok=True)
    ps_file = target_history / "project_state.json"
    ps_data = {}
    if ps_file.exists():
        try:
            with open(ps_file, "r", encoding="utf-8") as f:
                ps_data = json.load(f)
        except Exception:
            pass
    ps_data["project_name"] = req.new_name
    if req.path:
        ps_data["workspace_root"] = str(Path(req.path).resolve())
    with open(ps_file, "w", encoding="utf-8") as f:
        json.dump(ps_data, f, ensure_ascii=False, indent=2)

    # 4. 更新置顶信息映射
    if req.old_name in pins.get("pinned_projects", []):
        pins["pinned_projects"].remove(req.old_name)
        pins["pinned_projects"].append(req.new_name)
    if req.old_name in pins.get("pinned_sessions", {}):
        pins["pinned_sessions"][req.new_name] = pins["pinned_sessions"].pop(req.old_name)
    if req.old_name in pins.get("custom_titles", {}):
        pins["custom_titles"][req.new_name] = pins["custom_titles"].pop(req.old_name)
    save_pins_config(pins)

    # 若当前正在该工作区，同步更新
    if bridge.agent and bridge.agent.project_name == req.old_name:
        bridge.agent.session_manager.project_name = req.new_name
        bridge.agent.session_manager.history_dir = target_history
        if req.path and Path(req.path).exists():
            default_workspace.set_root(req.path)

    return {"success": True, "name": req.new_name, "path": req.path}

@app.post("/api/workspaces/pin")
def pin_workspace(req: WorkspacePinRequest):
    """置顶 / 取消置顶项目工作区"""
    pins = load_pins_config()
    p_list = pins.setdefault("pinned_projects", [])
    if req.pinned:
        if req.name not in p_list:
            p_list.append(req.name)
    else:
        if req.name in p_list:
            p_list.remove(req.name)
    save_pins_config(pins)
    return {"success": True, "pinned_projects": p_list}

@app.delete("/api/workspaces/delete")
def delete_workspace(req: WorkspaceDeleteRequest):
    """彻底删除指定工作区记录与历史目录"""
    pins = load_pins_config()
    del_name_clean = req.name.strip()
    del_name_lower = del_name_clean.lower()

    # 1. 清理置顶列表、排序列表与自定义元数据
    pins["pinned_projects"] = [p for p in pins.get("pinned_projects", []) if p.lower() != del_name_lower]
    pins["project_order"] = [p for p in pins.get("project_order", []) if p.lower() != del_name_lower]
    pins.setdefault("pinned_sessions", {}).pop(req.name, None)
    pins.setdefault("custom_titles", {}).pop(req.name, None)

    # 2. 登记到已删除列表，确保后续扫描彻底屏蔽
    deleted_list = pins.setdefault("deleted_projects", [])
    if del_name_clean not in deleted_list and not any(x.lower() == del_name_lower for x in deleted_list):
        deleted_list.append(del_name_clean)
    save_pins_config(pins)

    # 3. 从 ~/.super-harness/projects.json 磁盘注册表彻底移除 (大小写不敏感匹配)
    proj_map_file = Path.home() / ".super-harness" / "projects.json"
    if proj_map_file.exists():
        try:
            with open(proj_map_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
            projects = [p for p in projects if str(p.get("name", "")).strip().lower() != del_name_lower]
            with open(proj_map_file, "w", encoding="utf-8") as f:
                json.dump(projects, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 4. 彻底物理删除 history/ 下及 ~/.super-harness/workspace/ 下对应的项目子目录
    for h_dir in [HISTORY_ROOT, USER_DATA_ROOT / "workspace"]:
        if h_dir.exists():
            for d in list(h_dir.iterdir()):
                if d.is_dir() and d.name.lower() == del_name_lower:
                    try:
                        shutil.rmtree(d, ignore_errors=True)
                    except Exception:
                        pass

    # 5. 若删除的是当前激活工作区，切换到剩余项目或置空
    remaining_projects = get_all_projects_metadata()
    if remaining_projects:
        new_active = remaining_projects[0]
        new_root = Path(new_active["path"]).resolve() if new_active.get("path") else ROOT_DIR
        default_workspace.set_root(new_root)
        if bridge.agent:
            try:
                bridge.agent.switch_workspace(str(new_root))
            except Exception:
                pass
    else:
        default_workspace.set_root(ROOT_DIR)
        if bridge.agent:
            bridge.agent.session_manager.project_name = ""

    return {"success": True, "deleted": req.name}

@app.post("/api/sessions/rename")
def rename_session_title(req: SessionRenameRequest):
    """重命名会话标题"""
    pins = load_pins_config()
    proj_titles = pins.setdefault("custom_titles", {}).setdefault(req.project, {})
    proj_titles[req.session_id] = req.new_title.strip()
    save_pins_config(pins)
    return {"success": True, "new_title": req.new_title}

@app.post("/api/sessions/pin")
def pin_session(req: SessionPinRequest):
    """置顶 / 取消置顶指定会话"""
    pins = load_pins_config()
    proj_pins = pins.setdefault("pinned_sessions", {}).setdefault(req.project, [])
    if req.pinned:
        if req.session_id not in proj_pins:
            proj_pins.append(req.session_id)
    else:
        if req.session_id in proj_pins:
            proj_pins.remove(req.session_id)
    save_pins_config(pins)
    return {"success": True, "pinned": req.pinned}

@app.post("/api/sessions/clear")
def clear_session_content(req: SessionClearRequest):
    """清空指定会话的历史记录"""
    target_file = HISTORY_ROOT / req.project / f"{req.session_id}.jsonl"
    if target_file.exists():
        try:
            target_file.write_text("", encoding="utf-8")
        except Exception:
            pass
    if bridge.agent and bridge.agent.project_name == req.project:
        try:
            bridge.agent.context_manager.clear()
        except Exception:
            pass
    return {"success": True}

# 启动时自动迁移当前默认工作区及所有项目中遗留的附件目录
try:
    if hasattr(default_workspace, "root") and default_workspace.root and default_workspace.root.exists():
        migrate_legacy_attachments(default_workspace.root)
    for p in get_all_projects_metadata():
        if p.get("path") and Path(p["path"]).exists():
            migrate_legacy_attachments(Path(p["path"]))
except Exception:
    pass
