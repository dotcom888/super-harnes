# -*- coding: utf-8 -*-
"""
mcp/servers/calc_server.py:
独立 MCP 服务端 (计算器服务)。
通过标准输入输出 (stdio) 进行标准 JSON-RPC 2.0 通信，提供 tools/list 与 tools/call。
"""
import sys
import json
import ast
import operator

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def safe_calculate(expr: str) -> str:
    parsed = ast.parse(expr.strip(), mode="eval")
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            op = _SAFE_OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError("不支持的操作符")
            return op(_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = _SAFE_OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError("不支持的单目操作符")
            return op(_eval(node.operand))
        raise ValueError("不支持的表达式语法")
    return str(_eval(parsed.body))

SERVER_TOOLS = [
    {
        "name": "mcp_calculate",
        "description": "来自独立外部 MCP 服务的精确数学计算工具。支持加减乘除、幂运算与括号优先级。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，例如 '(128 * 4) + (1024 / 8)'"
                }
            },
            "required": ["expression"]
        }
    }
]

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
                        "serverInfo": {"name": "CalculatorMcpServer", "version": "1.0.0"},
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
                args = params.get("arguments", {})
                if tool_name == "mcp_calculate":
                    expr = args.get("expression", "")
                    try:
                        res = safe_calculate(expr)
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "content": [{"type": "text", "text": f"[MCP计算结果]: {res}"}]
                            }
                        }
                    except Exception as e:
                        response = {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "isError": True,
                                "content": [{"type": "text", "text": f"计算错误: {str(e)}"}]
                            }
                        }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"未知的 MCP 工具: {tool_name}"}
                    }
            else:
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as err:
            sys.stderr.write(f"Server exception: {err}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
