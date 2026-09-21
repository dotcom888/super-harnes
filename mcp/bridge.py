# -*- coding: utf-8 -*-
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from mcp.client import McpClient
from mcp.config import McpServerConfig, TrustLevel
from tools.registry import ToolRegistry, default_registry
from tools.policies import default_policy

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
TMP_OUTPUT_DIR = WORKSPACE_ROOT / ".super-harnes" / "tmp"
TMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 编译与代码诊断关键错误正则，优先锁定核心错误行与堆栈
ERROR_PATTERNS = [
    re.compile(r"(Traceback \(most recent call last\):[\s\S]+?)(?=\n\S|\Z)", re.IGNORECASE),
    re.compile(r"(\b(?:Error|Exception|FAILED|AssertionError|SyntaxError|TypeError|ValueError|IndexError):.*)", re.IGNORECASE),
    re.compile(r"(\b(?:\w+\.py|\w+\.ts|\w+\.rs|\w+\.go|\w+\.cpp|\w+\.c):\d+:\d+:.*error:.*)", re.IGNORECASE)
]

def semantic_output_clamp(raw_text: str, max_chars: int, server_id: str, tool_name: str) -> str:
    """
    语义化输出截断与全量持久化：
    1. 超限时将全量原始输出写入工作区临时文件，防止核心上下文永久丢失
    2. 优先通过正则捕捉 Traceback、Error、FAILED 等核心错误块，防止盲目比例截断切断报错关键行
    3. 保留文件路径供模型按需使用 read_file 工具深入排查
    """
    if len(raw_text) <= max_chars:
        return raw_text

    # 1. 全量持久化到临时日志文件
    timestamp = int(time.time() * 1000)
    spool_file = TMP_OUTPUT_DIR / f"mcp_{server_id}_{tool_name}_{timestamp}.log"
    spool_hint = ""
    try:
        spool_file.write_text(raw_text, encoding="utf-8", errors="replace")
        try:
            rel_path = spool_file.relative_to(WORKSPACE_ROOT)
        except Exception:
            rel_path = spool_file
        spool_hint = f"\n\n[提示: 外部 MCP 输出过长已精简。完整原始输出已存至: {rel_path}，如需定位细节请使用 read_file 查看]"
    except Exception:
        pass

    # 2. 语义搜索：尝试抓取核心错误块与堆栈
    matched_errors = []
    for pattern in ERROR_PATTERNS:
        matches = pattern.findall(raw_text)
        if matches:
            for m in matches[:3]:
                clean_m = m.strip()
                if clean_m and clean_m not in matched_errors:
                    matched_errors.append(clean_m)

    if matched_errors:
        error_summary = "\n--- [核心错误与堆栈提取] ---\n" + "\n".join(matched_errors)
        allowed_head_len = max(100, max_chars - len(error_summary) - len(spool_hint) - 120)
        head_part = raw_text[:allowed_head_len]
        return f"{head_part}\n\n... [已自动省略中间无关日志，保留核心错误诊断如下] ...\n{error_summary}{spool_hint}"

    # 3. 兜底策略：按行保留首尾（避免破坏单行语法），并附加文件路径提示
    lines = raw_text.splitlines()
    line_quota = max(4, int(max_chars / 150))
    head_lines = lines[:line_quota]
    tail_lines = lines[-line_quota:] if len(lines) > line_quota else []
    head = "\n".join(head_lines)
    tail = "\n".join(tail_lines)
    omitted_lines = max(0, len(lines) - len(head_lines) - len(tail_lines))

    return f"{head}\n\n... [外部 MCP 输出过长，已自动省略中间 {omitted_lines} 行] ...\n\n{tail}{spool_hint}"


class McpToolBridge:
    """
    加固型 MCP 工具桥接器：
    1. 命名空间唯一化：废除短别名注册，强制统一前缀 `mcp__{server_id}__{tool_name}`，节省 50% Schema Token
    2. 工具劫持防御 (Tool Shadowing Guard)：通过 register_mcp_proxy 严禁覆盖原生内置核心工具
    3. 语义化截断与落盘：保留堆栈报错信息并转存全量日志
    4. 信任级别与审批流集成 (Trust Level Policy)
    """
    def __init__(
        self,
        client: McpClient,
        config: Optional[McpServerConfig] = None,
        registry: ToolRegistry = default_registry
    ):
        self.client = client
        server_id = getattr(client, "server_name", "calculator" if "calc_server" in " ".join(client.command) else "mcp")
        self.config = config or McpServerConfig(server_id=server_id, command="python")
        self.registry = registry
        self.bridged_tool_names: List[str] = []

    def bridge(self) -> List[str]:
        # 1. 发送初始化协议
        self.client.send_request("initialize", timeout=self.config.timeout_seconds)

        # 2. 动态获取外部服务工具清单
        resp = self.client.send_request("tools/list", timeout=self.config.timeout_seconds)
        tools = resp.get("result", {}).get("tools", [])

        for tool_meta in tools:
            raw_name = tool_meta["name"]
            raw_desc = tool_meta.get("description", "外部 MCP 工具")
            input_schema = tool_meta.get("inputSchema", {})

            # 3. 命名空间强制前缀：mcp__{server_id}__{raw_name}
            namespaced_name = f"mcp__{self.config.server_id}__{raw_name}"
            enhanced_desc = f"[{self.config.server_id.upper()} MCP] {raw_desc}"

            internal_schema = {
                "type": "function",
                "function": {
                    "name": namespaced_name,
                    "description": enhanced_desc,
                    "parameters": input_schema
                }
            }

            # 4. 生成调用代理闭包函数
            def _create_proxy(target_raw_name: str, full_name: str) -> Callable:
                def proxy_func(**kwargs) -> str:
                    if self.config.trust_level == TrustLevel.BLOCKED:
                        return f"【安全拦截】：MCP 服务 '{self.config.server_id}' 处于禁用状态，禁止调用！"

                    if self.config.trust_level == TrustLevel.REQUIRE_APPROVAL:
                        reason = f"外部 MCP 工具 '{full_name}' 调用参数: {json.dumps(kwargs, ensure_ascii=False)}"
                        is_approved = default_policy.request_approval(full_name, reason)
                        if not is_approved:
                            return f"【用户拒绝】：用户在终端取消或拒绝了外部 MCP 工具 '{full_name}' 的执行申请。"

                    try:
                        call_resp = self.client.send_request(
                            "tools/call",
                            {"name": target_raw_name, "arguments": kwargs},
                            timeout=self.config.timeout_seconds
                        )
                    except TimeoutError:
                        return f"【MCP 超时】：外部服务 '{self.config.server_id}' 响应超时 ({self.config.timeout_seconds} 秒)，操作已中止。"
                    except Exception as err:
                        return f"【MCP 通信异常】：{type(err).__name__}: {str(err)}"

                    result_data = call_resp.get("result", {})
                    if result_data.get("isError"):
                        return f"【MCP 执行报错】：{json.dumps(result_data.get('content', []), ensure_ascii=False)}"

                    contents = result_data.get("content", [])
                    text_parts = [c.get("text", "") for c in contents if c.get("type") == "text"]
                    raw_result = "\n".join(text_parts) if text_parts else str(result_data)

                    # 5. 语义感知超长截断保护与本地转存
                    return semantic_output_clamp(
                        raw_result,
                        self.config.max_output_chars,
                        self.config.server_id,
                        target_raw_name
                    )

                proxy_func.__name__ = namespaced_name
                proxy_func.__doc__ = enhanced_desc
                return proxy_func

            # 仅向注册表注册 namespaced_name，彻底废除短别名 raw_name 注册！
            proxy = _create_proxy(raw_name, namespaced_name)
            self.registry.register_mcp_proxy(namespaced_name, proxy, internal_schema)
            self.bridged_tool_names.append(namespaced_name)

        return self.bridged_tool_names
