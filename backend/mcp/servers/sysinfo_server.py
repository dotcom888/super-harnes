# -*- coding: utf-8 -*-
"""
mcp/servers/sysinfo_server.py:
独立 MCP 服务端 (系统信息与环境探测服务)。
标准 JSON-RPC 2.0 stdio 服务，提供 get_current_time 和 get_system_info 工具。
"""
import sys
import json
import datetime
import platform

SERVER_TOOLS = [
    {
        "name": "get_current_time",
        "description": "来自独立 MCP 服务的精确时间工具。获取当前操作系统的日期、具体时间与星期。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_system_info",
        "description": "来自独立 MCP 服务的环境信息工具。获取当前操作系统的类型、版本架构以及 Python 版本。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

def handle_get_current_time() -> str:
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return f"当前系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')} ({weekday})"

def handle_get_system_info() -> str:
    return (
        f"操作系统: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"架构: {platform.machine()}\n"
        f"Python 版本: {platform.python_version()}"
    )

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "SystemInfoMcpServer", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": SERVER_TOOLS}
                }
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")

                if tool_name == "get_current_time":
                    output = handle_get_current_time()
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": output}]}
                    }
                elif tool_name == "get_system_info":
                    output = handle_get_system_info()
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": output}]}
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"未知工具: {tool_name}"}
                    }
            else:
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Sysinfo MCP Error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
