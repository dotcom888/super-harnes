# -*- coding: utf-8 -*-
import json
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional
from tools.registry import ToolRegistry, default_registry

class ToolExecutor:
    """
    工具执行器：负责安全调度、批量执行大模型发起的 tool_calls，
    支持纯只读工具的并发拉取（Concurrent Read-Only Execution）与精确顺序保全，
    将执行结果格式化为标准 OpenAI 消息格式。
    """
    def __init__(self, registry: ToolRegistry = default_registry, max_workers: int = 5, tool_timeout: Optional[float] = 60.0):
        self.registry = registry
        self.max_workers = max_workers
        self.tool_timeout = tool_timeout

    def _execute_single(self, tc: Any) -> Tuple[str, str, Dict[str, Any]]:
        """执行单个工具调用，返回 (func_name, args_str, msg_dict)"""
        if isinstance(tc, dict):
            func_name = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments", "")
            call_id = tc.get("id", "")
        else:
            func = getattr(tc, "function", None)
            func_name = getattr(func, "name", "") if func else ""
            raw_args = getattr(func, "arguments", "") if func else ""
            call_id = getattr(tc, "id", "")

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as err:
            error_msg = f"参数 JSON 格式解析失败: {str(err)}。传入参数为: {raw_args}"
            return func_name, str(raw_args), {
                "role": "tool",
                "tool_call_id": call_id,
                "content": error_msg
            }

        result = self.registry.execute(func_name, args)
        return func_name, json.dumps(args, ensure_ascii=False), {
            "role": "tool",
            "tool_call_id": call_id,
            "content": str(result)
        }

    def _execute_and_log(self, tc: Any, verbose: bool = True) -> Dict[str, Any]:
        if isinstance(tc, dict):
            func_name = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments", "")
        else:
            func = getattr(tc, "function", None)
            func_name = getattr(func, "name", "") if func else ""
            raw_args = getattr(func, "arguments", "") if func else ""

        if verbose:
            print(f"  [Action] 正在执行工具 -> 【{func_name}】")
            try:
                parsed_args = json.loads(raw_args) if raw_args else {}
                print(f"           输入参数: {json.dumps(parsed_args, ensure_ascii=False)}")
            except Exception:
                print(f"           输入参数: {raw_args}")

        func_name, args_str, msg = self._execute_single(tc)

        if verbose:
            content = msg.get("content", "")
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"  [Observation] 工具返回结果 -> {preview}")

        return msg

    def execute_tool_calls(self, tool_calls: List[Any], verbose: bool = True) -> List[Dict[str, Any]]:
        """
        批量执行由模型触发的 tool_calls：
        - 连续的纯只读工具批次通过 ThreadPoolExecutor 并发拉取，大幅消除多文件探索延迟；
        - 写操作工具（修改磁盘或系统环境）采用串行栅栏（Barrier）；
        - 严格保证返回消息序列与传入 tool_calls 的原始索引一一对应。
        """
        if not tool_calls:
            return []

        results: List[Optional[Dict[str, Any]]] = [None] * len(tool_calls)

        idx = 0
        while idx < len(tool_calls):
            tc = tool_calls[idx]
            fname = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(getattr(tc, "function", None), "name", "")

            if self.registry.is_read_only(fname):
                # 收集后续连续的只读工具调用
                read_chunk = [(idx, tc)]
                next_idx = idx + 1
                while next_idx < len(tool_calls):
                    next_tc = tool_calls[next_idx]
                    next_fname = next_tc.get("function", {}).get("name", "") if isinstance(next_tc, dict) else getattr(getattr(next_tc, "function", None), "name", "")
                    if self.registry.is_read_only(next_fname):
                        read_chunk.append((next_idx, next_tc))
                        next_idx += 1
                    else:
                        break

                if len(read_chunk) > 1:
                    if verbose:
                        chunk_names = ", ".join(
                            f"【{t[1].get('function', {}).get('name', '') if isinstance(t[1], dict) else getattr(getattr(t[1], 'function', None), 'name', '')}】"
                            for t in read_chunk
                        )
                        print(f"  [Action] 并发并行执行 {len(read_chunk)} 个只读工具 -> {chunk_names}")

                    workers = min(self.max_workers, len(read_chunk))
                    pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
                    future_map = {
                        pool.submit(self._execute_single, item_tc): (item_idx, item_tc)
                        for item_idx, item_tc in read_chunk
                    }
                    try:
                        for future, (item_idx, item_tc) in future_map.items():
                            try:
                                _, _, msg = future.result(timeout=self.tool_timeout)
                                results[item_idx] = msg
                            except concurrent.futures.TimeoutError:
                                call_id = item_tc.get("id", "") if isinstance(item_tc, dict) else getattr(item_tc, "id", "")
                                results[item_idx] = {
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": f"【执行超时】：工具执行超时（超过 {self.tool_timeout} 秒）。"
                                }
                            except Exception as exc:
                                call_id = item_tc.get("id", "") if isinstance(item_tc, dict) else getattr(item_tc, "id", "")
                                results[item_idx] = {
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": f"【并发执行异常】：{type(exc).__name__}: {str(exc)}"
                                }
                    finally:
                        pool.shutdown(wait=False)

                    if verbose:
                        for item_idx, item_tc in read_chunk:
                            msg = results[item_idx]
                            content = msg.get("content", "") if msg else ""
                            preview = content[:200] + "..." if len(content) > 200 else content
                            print(f"  [Observation] [只读并发完成] -> {preview}")

                    idx = next_idx
                else:
                    results[idx] = self._execute_and_log(tc, verbose=verbose)
                    idx += 1
            else:
                results[idx] = self._execute_and_log(tc, verbose=verbose)
                idx += 1

        # 兜底校验：确保每个 tool_call 都有对应的 tool 消息，绝对不留空，杜绝大模型 API 报 400 缺少 tool_call_id
        for i, tc in enumerate(tool_calls):
            if results[i] is None:
                call_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                results[i] = {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": "【执行异常】：未能获取工具执行结果。"
                }

        return results

default_executor = ToolExecutor()
