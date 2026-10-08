# -*- coding: utf-8 -*-
"""
server/app.py: FastAPI 服务端 (为 Electron 客户端提供多项目历史扫描、自定义模型映射与 AUTO 模式通信)
"""
import os
import sys
import json
import time
import asyncio
import shutil
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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.agent_bridge import bridge, format_tool_display
from tools.framework.workspace import default_workspace
from tools.framework.policies import default_policy
from skills import default_skill_manager

app = FastAPI(title="Super-Harnes Agent Desktop API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_DATA_ROOT = Path.home() / ".super-harnes"
USER_DATA_ROOT.mkdir(parents=True, exist_ok=True)
USER_CONFIG_DIR = USER_DATA_ROOT / "config"
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
USER_MODELS_CONFIG_PATH = USER_CONFIG_DIR / "models_config.json"

MODELS_CONFIG_PATH = ROOT_DIR / "config" / "models_config.json"
USER_HISTORY_ROOT = USER_DATA_ROOT / "history"
USER_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)

if getattr(sys, "frozen", False):
    # 打包脱机运行模式：用户聊天历史存储在用户数据目录，初始状态为空白纯净
    HISTORY_ROOT = USER_HISTORY_ROOT
else:
    HISTORY_ROOT = ROOT_DIR / "history" 

# ================= 数据模型定义 =================
class PromptRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    permission_mode: Optional[str] = "auto"
    session_id: Optional[str] = None
    project: Optional[str] = None

class SessionActionRequest(BaseModel):
    session_id: str
    project: Optional[str] = None

class WorkspaceSwitchRequest(BaseModel):
    path: Optional[str] = None
    name: Optional[str] = None

class WorkspaceAddRequest(BaseModel):
    path: str

class ModelSwitchRequest(BaseModel):
    model: str

class ProviderConfigRequest(BaseModel):
    id: Optional[str] = None
    name: str
    base_url: str
    api_key: str = ""
    models: List[str] = []
    is_custom: bool = True

class ModeSwitchRequest(BaseModel):
    mode: str

# ================= 辅助函数：模型与提供方管理 =================
def load_models_config() -> Dict[str, Any]:
    """读取模型与提供方配置 (优先用户数据持久化目录，回退安装包内置配置)"""
    for p in (USER_MODELS_CONFIG_PATH, MODELS_CONFIG_PATH):
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
    """持久化保存模型与提供方配置 (双重写入用户目录与本地开发目录)"""
    for p in (USER_MODELS_CONFIG_PATH, MODELS_CONFIG_PATH):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def get_active_models_list() -> List[str]:
    """仅返回已配置有效 API Key 的模型列表，未配置密钥时严格返回空列表"""
    cfg = load_models_config()
    active_models = []
    
    # 1. 检查环境变量中是否配置了有效的 API 密钥
    env_key = os.getenv("LLM_API_KEY", "").strip()
    env_model = os.getenv("LLM_MODEL", "").strip()
    if env_key and env_model:
        active_models.append(env_model)

    # 2. 从提供方中提取已填写有效 API Key 的模型
    for p in cfg.get("providers", []):
        if p.get("api_key", "").strip():
            for m in p.get("models", []):
                if m and m not in active_models:
                    active_models.append(m)

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

        is_pinned = sid in pinned_sids
        display_title = custom_titles.get(sid) or current_goal or sid
        sessions.append({
            "session_id": sid,
            "turn_count": max(turn_count, 1),
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
    """扫描 history/ 目录，自动发现包含聊天历史的全部项目 (过滤已删除项目)"""
    projects = []
    known_names = set()

    pins = load_pins_config()
    deleted_names = set(pins.get("deleted_projects", []))

    # 1. 扫描 history/ 下的所有目录
    if HISTORY_ROOT.exists():
        for d in HISTORY_ROOT.iterdir():
            if d.is_dir():
                pname = d.name
                if pname in deleted_names:
                    continue
                known_names.add(pname)
                proj_sessions = scan_project_sessions(d)
                
                # 尝试获取对应工作区根路径
                proj_path = ""
                ps_file = d / "project_state.json"
                if ps_file.exists():
                    try:
                        with open(ps_file, "r", encoding="utf-8") as psf:
                            ps_data = json.load(psf)
                            proj_path = ps_data.get("workspace_root", "")
                    except Exception:
                        pass

                if not proj_path and pname == default_workspace.root.name:
                    proj_path = str(default_workspace.root)

                projects.append({
                    "name": pname,
                    "path": proj_path,
                    "session_count": len(proj_sessions),
                    "sessions": proj_sessions
                })

    # 2. 检查注册在 ~/.super-harnes/projects.json 的磁盘工程
    proj_map_file = Path.home() / ".super-harnes" / "projects.json"
    if proj_map_file.exists():
        try:
            with open(proj_map_file, "r", encoding="utf-8") as f:
                extra_projects = json.load(f)
                for ep in extra_projects:
                    ep_name = ep.get("name")
                    if ep_name and ep_name not in known_names:
                        if ep_name in deleted_names:
                            continue
                        known_names.add(ep_name)
                        ep_dir = HISTORY_ROOT / ep_name
                        ep_sessions = scan_project_sessions(ep_dir)
                        projects.append({
                            "name": ep_name,
                            "path": ep.get("path", ""),
                            "session_count": len(ep_sessions),
                            "sessions": ep_sessions
                        })
        except Exception:
            pass

    # 确保当前活跃工作区在列表中 (排除打包内部临时目录)
    cur_name = default_workspace.root.name
    if cur_name.lower() not in ("super-server", "bin", "resources", "_internal", "workspace") and cur_name not in known_names and cur_name not in deleted_names:
        cur_sessions = scan_project_sessions(HISTORY_ROOT / cur_name)
        projects.insert(0, {
            "name": cur_name,
            "path": str(default_workspace.root),
            "session_count": len(cur_sessions),
            "sessions": cur_sessions
        })

    pins = load_pins_config()
    pinned_projs = pins.get("pinned_projects", [])
    for p in projects:
        p["is_pinned"] = p["name"] in pinned_projs
    projects.sort(key=lambda x: (1 if x.get("is_pinned") else 0, x.get("session_count", 0)), reverse=True)
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

            elif t == "assistant_message":
                content = data.get("content", "")
                tcs = data.get("tool_calls", [])
                
                # 捕获思考内容与助理推理步骤
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
                elif content and tcs:
                    if not turns_map[tid]["thought"]:
                        turns_map[tid]["thought"] = content
                    turns_map[tid]["steps"].append({
                        "id": f"th_{len(turns_map[tid]['steps'])}",
                        "type": "assistant",
                        "thought": content,
                        "timestamp": row.get("timestamp", time.time())
                    })
                elif content and not tcs:
                    turns_map[tid]["assistant_response"] = content

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

            elif t == "turn_finished":
                wm = data.get("working_memory", {})
                working_memory_last = wm
                if wm.get("current_goal") and not turns_map[tid]["user_prompt"]:
                    turns_map[tid]["user_prompt"] = wm.get("current_goal")

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
    """获取所有已配置有效的大模型列表供无缝切换（未配置时返回空列表与空字符串）"""
    cfg = load_models_config()
    active_models = get_active_models_list()
    cur = cfg.get("current_model", "")
    if cur not in active_models:
        cur = active_models[0] if active_models else ""
    return {
        "current_model": cur,
        "models": active_models
    }

@app.post("/api/models/switch")
def switch_model(req: ModelSwitchRequest):
    """切换当前智能体使用的大模型"""
    cfg = load_models_config()
    cfg["current_model"] = req.model
    save_models_config(cfg)

    if bridge.agent:
        bridge.agent.model = req.model
    return {"success": True, "current_model": req.model}

@app.get("/api/models/providers")
def get_providers():
    """获取所有模型提供方（对标设置页面：包含内置提供方与自定义提供方）"""
    cfg = load_models_config()
    providers_list = []
    for p in cfg.get("providers", []):
        key = p.get("api_key", "")
        # 脱敏展示
        masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("已配置" if key else "")
        status = "connected" if key or p.get("status") == "connected" else "unconfigured"
        providers_list.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "base_url": p.get("base_url"),
            "api_key_masked": masked_key,
            "models": p.get("models", []),
            "is_custom": p.get("is_custom", True),
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

    for idx, p in enumerate(providers):
        if p.get("id") == pid or p.get("name") == req.name:
            providers[idx] = {
                "id": pid,
                "name": req.name,
                "base_url": req.base_url,
                "api_key": req.api_key or p.get("api_key", ""),
                "models": req.models,
                "is_custom": req.is_custom,
                "status": "connected" if req.api_key or p.get("api_key") else "unconfigured"
            }
            found = True
            break

    if not found:
        providers.append({
            "id": pid,
            "name": req.name,
            "base_url": req.base_url,
            "api_key": req.api_key,
            "models": req.models,
            "is_custom": req.is_custom,
            "status": "connected" if req.api_key else "unconfigured"
        })

    cfg["providers"] = providers
    save_models_config(cfg)
    return {"success": True, "providers": providers, "active_models": get_active_models_list()}

@app.delete("/api/models/providers/{provider_id}")
def delete_provider(provider_id: str):
    """删除自定义提供方"""
    cfg = load_models_config()
    cfg["providers"] = [p for p in cfg.get("providers", []) if p.get("id") != provider_id]
    save_models_config(cfg)
    return {"success": True, "active_models": get_active_models_list()}

@app.get("/api/workspaces")
def get_workspaces():
    """获取所有已扫描到的项目与工作区列表（包含磁盘项目的全部聊天历史）"""
    all_projects = get_all_projects_metadata()
    active_name = default_workspace.root.name
    if active_name.lower() in ("super-server", "bin", "resources", "_internal", "workspace") or not any(p["name"] == active_name for p in all_projects):
        sh_proj = next((p for p in all_projects if p["name"] == "super-harnes"), None)
        if sh_proj:
            active_name = "super-harnes"
        elif all_projects:
            active_name = all_projects[0]["name"]
        else:
            active_name = "super-harnes"

    current_root = str(default_workspace.root)
    return {
        "current": current_root,
        "name": active_name,
        "projects": all_projects
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
        return {"success": True, "workspace_path": str(new_root), "name": new_root.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/workspaces/add")
def add_workspace(req: WorkspaceAddRequest):
    """选择磁盘项目并注册为新工作区"""
    p = Path(req.path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail="指定的磁盘目录不存在或不是文件夹")

    # 注册到 ~/.super-harnes/projects.json
    proj_map_file = Path.home() / ".super-harnes" / "projects.json"
    proj_map_file.parent.mkdir(parents=True, exist_ok=True)
    projects = []
    if proj_map_file.exists():
        try:
            with open(proj_map_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
        except Exception:
            pass

    # 避免重复
    if not any(item.get("path") == str(p) for item in projects):
        projects.append({"name": p.name, "path": str(p)})
        with open(proj_map_file, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)

    # 自动创建对应项目的历史目录
    (HISTORY_ROOT / p.name).mkdir(parents=True, exist_ok=True)

    # 切换到该工作区
    if bridge.agent:
        bridge.agent.switch_workspace(str(p))

    return {
        "success": True,
        "name": p.name,
        "path": str(p),
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

@app.post("/api/sessions/create")
def create_session(req: Optional[SessionActionRequest] = None):
    """创建全新会话"""
    proj_name = req.project if req and req.project else default_workspace.root.name
    sid = req.session_id if req and req.session_id else f"session_{int(time.time())}"
    
    # 确保磁盘目录存在
    (HISTORY_ROOT / proj_name).mkdir(parents=True, exist_ok=True)

    if bridge.agent and proj_name == default_workspace.root.name:
        bridge.agent.create_session(sid)

    return {"success": True, "session_id": sid, "project": proj_name}

@app.delete("/api/sessions/delete")
def delete_session(req: SessionActionRequest):
    """删除会话"""
    proj_name = req.project or default_workspace.root.name
    target_file = HISTORY_ROOT / proj_name / f"{req.session_id}.jsonl"
    if target_file.exists():
        try:
            target_file.unlink()
        except Exception:
            pass
    return {"success": True}

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

@app.get("/api/mcp")
def get_mcp():
    """获取外部 MCP 扩展服务状态（包含服务标识、绑定脚本与工具清单）"""
    if not bridge.agent:
        return {"clients": [], "tools": [], "servers_detail": []}
    all_tools = bridge.agent.executor.registry.get_tool_names()
    mcp_tools = [t for t in all_tools if t.startswith("mcp__")]
    clients = list(bridge.agent.mcp_manager.clients.keys())
    servers_detail = []
    for sid, cfg in getattr(bridge.agent.mcp_manager, "configs", {}).items():
        tools_for_srv = [t for t in mcp_tools if f"mcp__{sid}__" in t or sid in t]
        servers_detail.append({
            "server_id": sid,
            "command": cfg.command,
            "args": cfg.args,
            "trust_level": cfg.trust_level,
            "status": "connected" if sid in clients else "unconfigured",
            "tools": tools_for_srv
        })
    return {
        "clients": clients,
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """全双工实时通信：接收 Prompt 并向前端持续广播工具流与执行结果"""
    await websocket.accept()
    loop = asyncio.get_running_loop()

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
                if not prompt_text:
                    continue

                model = payload.get("model")
                perm_mode = payload.get("permission_mode", "auto")
                session_id = payload.get("session_id", "default")
                project_name = payload.get("project_name", default_workspace.root.name)

                await websocket.send_json({
                    "event": "prompt_received",
                    "prompt": prompt_text,
                    "session_id": session_id,
                    "project": project_name,
                    "timestamp": asyncio.get_event_loop().time()
                })

                def emit_event(ev: Dict[str, Any]):
                    ev.setdefault("session_id", session_id)
                    ev.setdefault("project", project_name)
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json(ev),
                        loop
                    )

                try:
                    await bridge.execute_prompt_stream(
                        prompt=prompt_text,
                        event_callback=emit_event,
                        model=model,
                        permission_mode=perm_mode,
                        session_id=session_id,
                        project_name=project_name
                    )
                except Exception as err:
                    await websocket.send_json({
                        "event": "error",
                        "session_id": session_id,
                        "project": project_name,
                        "message": str(err)
                    })

            elif msg_type == "abort":
                session_id = payload.get("session_id", "default")
                project_name = payload.get("project_name", default_workspace.root.name)
                bridge.abort_session(session_id, project_name)
                await websocket.send_json({
                    "event": "assistant_response",
                    "content": "【用户已手动暂停】已终止当前轮次的推理与工具执行。",
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

PINS_FILE = ROOT_DIR / "history" / "pins_config.json"

def load_pins_config() -> Dict[str, Any]:
    if PINS_FILE.exists():
        try:
            with open(PINS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pinned_projects": [], "pinned_sessions": {}, "custom_titles": {}}

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
    proj_map_file = Path.home() / ".super-harnes" / "projects.json"
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
    """彻底删除指定工作区记录及历史数据"""
    pins = load_pins_config()
    
    # 1. 从置顶列表与自定义元数据中清理
    if req.name in pins.get("pinned_projects", []):
        pins["pinned_projects"].remove(req.name)
    pins.setdefault("pinned_sessions", {}).pop(req.name, None)
    pins.setdefault("custom_titles", {}).pop(req.name, None)

    # 2. 登记至已删除黑名单，永久杜绝缓存死灰复燃
    deleted_list = pins.setdefault("deleted_projects", [])
    if req.name not in deleted_list:
        deleted_list.append(req.name)
    save_pins_config(pins)

    # 3. 从 ~/.super-harnes/projects.json 磁盘注册表移除
    proj_map_file = Path.home() / ".super-harnes" / "projects.json"
    if proj_map_file.exists():
        try:
            with open(proj_map_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
            projects = [p for p in projects if p.get("name") != req.name]
            with open(proj_map_file, "w", encoding="utf-8") as f:
                json.dump(projects, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 4. 彻底物理清除 history/ 下对应的项目子目录
    target_dir = HISTORY_ROOT / req.name
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir, ignore_errors=True)
        except Exception as e:
            pass

    # 5. 若删除的是当前正处于的工作区，自动重置激活工作区到主仓库根目录
    if default_workspace.root.name == req.name:
        default_workspace.set_root(ROOT_DIR)
    if bridge.agent and getattr(bridge.agent, "project_name", "") == req.name:
        try:
            bridge.agent.switch_workspace(ROOT_DIR)
        except Exception:
            pass

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
