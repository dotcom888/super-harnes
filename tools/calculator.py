# -*- coding: utf-8 -*-
import ast
import operator
import math
from tools.registry import register_tool

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

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}

def _eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = _SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的单目运算符: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS and not callable(_SAFE_FUNCTIONS[node.id]):
            return _SAFE_FUNCTIONS[node.id]
        raise ValueError(f"未知的常量名: {node.id}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            args = [_eval_node(arg) for arg in node.args]
            return func(*args)
        raise ValueError("不支持的函数调用")
    else:
        raise ValueError(f"不允许的表达式语法: {type(node).__name__}")

# 使用 register_tool 一行完成工具定义与参数说明
@register_tool(
    name="calculate",
    description="用于精确计算数学表达式。当用户问题涉及四则运算、乘方、开方、三角函数等数学计算时使用此工具。",
    param_descriptions={
        "expression": "要计算的数学表达式字符串，例如 '(123 + 456) * 78' 或 'sqrt(144)'"
    }
)
def calculate(expression: str) -> str:
    """安全计算数学表达式并返回结果"""
    clean_expr = expression.strip()
    parsed = ast.parse(clean_expr, mode="eval")
    result = _eval_node(parsed.body)
    return str(result)
