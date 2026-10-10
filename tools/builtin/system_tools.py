# -*- coding: utf-8 -*-
"""
tools/builtin/system_tools.py:
系统通用内置工具：
1. calculate: 安全可靠的精确数学计算引擎 (由原 MCP 迁入内置，消除进程 IPC 开销)
2. get_current_time: 获取宿主机当前的年月日、时分秒与星期
3. get_system_info: 获取宿主机操作系统平台、内核版本与 Python 运行时环境
"""
import ast
import operator
import datetime
import platform
from typing import Optional
from tools.registry import default_registry

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

def _safe_eval(expr: str) -> str:
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

@default_registry.register(
    name="calculate",
    description="内置精确数学计算工具。支持加减乘除、求余、幂运算与括号优先级，适用于数值统计、换算与精度计算。",
    param_descriptions={
        "expression": "要计算的数学表达式字符串，例如 '(128 * 4) + (1024 / 8)'"
    },
        is_read_only=True
)
def calculate(expression: str) -> str:
    """计算数学表达式并返回精确结果"""
    try:
        res = _safe_eval(expression)
        return f"【计算结果】: {res}"
    except Exception as e:
        return f"【计算失败】: {str(e)}"

@default_registry.register(
    name="get_current_time",
    description="内置系统时间获取工具。获取当前宿主机操作系统的实时日期、精准时间与星期几。",
    param_descriptions={},
        is_read_only=True
)
def get_current_time() -> str:
    """获取当前系统时间与星期"""
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return f"【当前系统时间】: {now.strftime('%Y-%m-%d %H:%M:%S')} ({weekday})"

@default_registry.register(
    name="get_system_info",
    description="内置宿主机环境信息工具。获取宿主机操作系统名称、版本架构及 Python 解释器环境。",
    param_descriptions={},
        is_read_only=True
)
def get_system_info() -> str:
    """获取宿主机操作系统与运行时信息"""
    return (
        f"【操作系统环境】:\n"
        f"- 系统平台: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"- 硬件架构: {platform.machine()}\n"
        f"- Python版本: {platform.python_version()}"
    )
