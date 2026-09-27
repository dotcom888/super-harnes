# -*- coding: utf-8 -*-
"""
tests/test_output_optimization_and_tool_precision.py:
工具精准选型与海量输出四层漏斗转存架构专项测试集
验证：
1. 工具 Schema 反向约束 (Negative Constraints) 与互斥指引
2. 运行时 Shell 防呆重定向 (Smart Redirector) 与合法命令放行
3. 通用输出优化器 (output_clamp):
   - 物理全量安全落盘 (Spillover Buffer)
   - 追查透镜指针 (Lens Pointer)
   - 关键报错与 Traceback 核心语义提取
   - 检索海量命中的文件热力聚合卡片
   - 动态上下文水位预算配额联动
4. Agent 单步工具输出保护与动态水位联动
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.framework.workspace import default_workspace, set_workspace_root
from tools.framework.output_clamp import (
    spool_to_disk,
    clamp_shell_output,
    clamp_search_output,
    clamp_generic_output,
    get_dynamic_max_chars,
    cleanup_old_spool_files,
    get_tmp_spool_dir
)
from tools.builtin.shell_tool import run_shell, _check_shell_misuse
from tools.builtin.file_tools import read_file, write_file
from tools.builtin.patch_tool import apply_patch
from tools.builtin.search_tools import grep_text, find_by_name
from tools.registry import default_registry
from core.agent import ReActAgent
from core.prompt import build_system_prompt

class TestToolSelectionPrecision(unittest.TestCase):
    """测试工具选型精度：Schema 反向约束、Prompt 决策矩阵与运行时防呆重定向"""

    def setUp(self):
        self.orig_root = default_workspace.root
        self.temp_dir = tempfile.mkdtemp(prefix="test_precision_")
        self.temp_path = Path(self.temp_dir).resolve()
        set_workspace_root(self.temp_path)

    def tearDown(self):
        set_workspace_root(self.orig_root)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        leaked = Path(self.orig_root) / "history" / self.temp_path.name
        if leaked.exists():
            shutil.rmtree(leaked, ignore_errors=True)

    def test_schema_negative_constraints_present(self):
        """验证所有核心工具的 JSON Schema 中均包含反向互斥约束与场景指引"""
        schemas = default_registry.get_schemas()
        schema_map = {s["function"]["name"]: s["function"]["description"] for s in schemas}

        # 1. run_shell 应严禁替代 read_file / grep_text / find_by_name
        shell_desc = schema_map.get("run_shell", "")
        self.assertIn("反向指引", shell_desc)
        self.assertIn("严禁使用此工具查看文件内容", shell_desc)
        self.assertIn("read_file", shell_desc)
        self.assertIn("grep_text", shell_desc)

        # 2. read_file 应警示未知大文件通读，提倡 view_file_outline 先行
        read_desc = schema_map.get("read_file", "")
        self.assertIn("view_file_outline", read_desc)
        self.assertIn("严禁盲目直接从第 1 行读取全文", read_desc)

        # 3. write_file vs apply_patch 互斥定义
        write_desc = schema_map.get("write_file", "")
        patch_desc = schema_map.get("apply_patch", "")
        self.assertIn("全新创建文件", write_desc)
        self.assertIn("严禁为了微调几行现有代码而调用此工具整盘覆写", write_desc)
        self.assertIn("apply_patch", write_desc)
        self.assertIn("局部精准修改", patch_desc)
        self.assertIn("SEARCH/REPLACE", patch_desc)

        # 4. grep_text 与 find_by_name 场景分工
        grep_desc = schema_map.get("grep_text", "")
        find_desc = schema_map.get("find_by_name", "")
        self.assertIn("专用于定位变量、函数定义、类名或报错文本", grep_desc)
        self.assertIn("专用于定位未知文件路径", find_desc)

    def test_prompt_decision_matrix_injected(self):
        """验证系统提示词中包含探索、编码、验证三阶段工具意图决策树"""
        prompt = build_system_prompt()
        self.assertIn("开发者动作与工具选型决策矩阵", prompt)
        self.assertIn("探索定位阶段", prompt)
        self.assertIn("编码实现阶段", prompt)
        self.assertIn("验证闭环阶段", prompt)
        self.assertIn("find_by_name", prompt)
        self.assertIn("apply_patch", prompt)

    def test_shell_misuse_redirector_cat_head_tail(self):
        """测试运行时误用 Shell 读取文件被友好拦截并重定向"""
        # 1. cat 拦截
        res_cat = run_shell("cat core/agent.py")
        self.assertIn("【工具选型重定向建议】", res_cat)
        self.assertIn("read_file(file_path='core/agent.py')", res_cat)

        # 2. type 拦截
        res_type = run_shell("type README.md")
        self.assertIn("【工具选型重定向建议】", res_type)
        self.assertIn("read_file(file_path='README.md')", res_type)

        # 3. head 拦截
        res_head = run_shell("head -n 20 app.py")
        self.assertIn("【工具选型重定向建议】", res_head)
        self.assertIn("read_file(file_path='app.py')", res_head)

    def test_shell_misuse_redirector_grep_and_find(self):
        """测试运行时误用 Shell grep / find 被友好拦截并重定向"""
        # 1. grep 拦截
        res_grep = run_shell("grep -rn 'def run' .")
        self.assertIn("【工具选型重定向建议】", res_grep)
        self.assertIn("grep_text", res_grep)

        # 2. find -name 拦截
        res_find = run_shell("find . -name '*.py'")
        self.assertIn("【工具选型重定向建议】", res_find)
        self.assertIn("find_by_name", res_find)

    def test_shell_valid_commands_allowed(self):
        """测试合法的正常命令与包含管道的复合操作不被误杀"""
        # 1. 普通 git 或 python
        res_status = run_shell("git status")
        self.assertNotIn("【工具选型重定向建议】", res_status)

        # 2. echo 输出
        res_echo = run_shell("echo hello world")
        self.assertIn("hello world", res_echo)


class TestSpoolingAndOutputOptimization(unittest.TestCase):
    """测试海量输出转存 (Spooling)、追查透镜与语义特征提取"""

    def setUp(self):
        self.orig_root = default_workspace.root
        self.temp_dir = tempfile.mkdtemp(prefix="test_spool_")
        self.temp_path = Path(self.temp_dir).resolve()
        set_workspace_root(self.temp_path)

    def tearDown(self):
        set_workspace_root(self.orig_root)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        leaked = Path(self.orig_root) / "history" / self.temp_path.name
        if leaked.exists():
            shutil.rmtree(leaked, ignore_errors=True)

    def test_disk_spooling_creates_file_and_lens_hint(self):
        """验证大输出物理全量落盘并生成追查透镜提示"""
        large_output = "line: data\n" * 1000
        spool_file, lens_hint = spool_to_disk(large_output, tool_name="test_tool")
        
        self.assertIsNotNone(spool_file)
        self.assertTrue(spool_file.exists())
        self.assertEqual(spool_file.read_text(encoding="utf-8"), large_output)
        
        # 验证透镜提示词包含行数、大小与追查指引
        self.assertIn("系统提示: 完整原始输出", lens_hint)
        self.assertIn("1000 行", lens_hint)
        self.assertIn("read_file", lens_hint)
        self.assertIn("grep_text", lens_hint)

    def test_clamp_shell_output_preserves_traceback_and_failures(self):
        """验证海量测试日志在截断时，核心 Traceback、FAILED 与尾部 Summary 被完整保留"""
        lines = ["PASSED test_case_normal.py::test_ok" for _ in range(1200)]
        # 在第 800 行（正中间）注入关键报错，旧版暴力截断会导致其彻底丢失
        error_block = (
            "=================================== FAILURES ===================================\n"
            "________________________________ test_critical _________________________________\n"
            "Traceback (most recent call last):\n"
            "  File 'core/agent.py', line 123, in test_critical\n"
            "    assert result == 42\n"
            "AssertionError: expected 42 but got 0\n"
        )
        lines.insert(800, error_block)
        lines.append("=== 1 failed, 1200 passed in 12.5s ===")
        huge_log = "\n".join(lines)
        
        self.assertGreater(len(huge_log), 40000)

        clamped = clamp_shell_output(huge_log, max_chars=6000, tool_name="run_shell")

        # 1. 严格受限：不超过 max_chars
        self.assertLessEqual(len(clamped), 6000)
        # 2. 核心报错未丢失
        self.assertIn("核心错误与堆栈提取", clamped)
        self.assertIn("Traceback (most recent call last):", clamped)
        self.assertIn("AssertionError: expected 42 but got 0", clamped)
        # 3. 包含折叠提示与透镜路径
        self.assertIn("已保护性省略中间日志", clamped)
        self.assertIn("系统提示: 完整原始输出", clamped)

    def test_clamp_search_output_frequency_aggregation(self):
        """验证 grep 命中上百条时，自动转为文件热力分布聚合卡片与代表性样本"""
        matches = []
        # 模拟分布在不同文件的 80 处匹配
        for i in range(40):
            matches.append(f"core/agent.py:{i*5}: def run_step_{i}():")
        for i in range(25):
            matches.append(f"tools/executor.py:{i*3}: def execute_{i}():")
        for i in range(15):
            matches.append(f"context/manager.py:{i*2}: class ContextManager_{i}:")

        raw_text = "\n".join(matches)
        clamped = clamp_search_output(
            raw_text,
            matches=matches,
            max_chars=4000,
            max_samples=10,
            keyword="def",
            file_pattern="*.py"
        )

        # 1. 聚合卡片包含命中统计与高频文件
        self.assertIn("代码搜索聚合", clamped)
        self.assertIn("共找到 80 处匹配，分布在 3 个文件中", clamped)
        self.assertIn("`core/agent.py` (40 处)", clamped)
        self.assertIn("`tools/executor.py` (25 处)", clamped)
        # 2. 代表性样本限制展示
        self.assertIn("代表性前 10 条匹配样本", clamped)
        self.assertIn("检索优化建议", clamped)
        # 3. 附带全量落盘追查透镜
        self.assertIn("系统提示: 完整原始输出", clamped)

    def test_dynamic_watermark_quota_allocation(self):
        """测试不同上下文水位下的动态字符配额"""
        green_quota = get_dynamic_max_chars("GREEN")
        yellow_quota = get_dynamic_max_chars("YELLOW")
        red_quota = get_dynamic_max_chars("RED")

        self.assertGreater(green_quota, yellow_quota)
        self.assertGreater(yellow_quota, red_quota)
        self.assertEqual(green_quota, 20000)
        self.assertEqual(yellow_quota, 7000)
        self.assertEqual(red_quota, 2500)

    def test_agent_protect_tool_result_watermark_linkage(self):
        """验证 ReActAgent._protect_tool_result 动态感知红区水位紧缩"""
        agent = ReActAgent(model="mock")
        huge_text = "log message normal status\n" * 500  # 约 13000 字符

        # 绿区水位 (20000 字符)：13000 字符充盈放行
        green_res = agent._protect_tool_result(huge_text, zone="GREEN")
        self.assertEqual(green_res, huge_text)

        # 红区水位 (2500 字符)：自动强力压缩并落盘
        red_res = agent._protect_tool_result(huge_text, zone="RED")
        self.assertLessEqual(len(red_res), 2500)
        self.assertIn("系统提示: 完整原始输出", red_res)



    def test_anchor_indexed_lens_generation(self):
        """方案 1 测试：验证超大日志截断时，透镜提示附带确切报错行号锚点与直接调阅指引"""
        lines = ['log normal ok info\n' for _ in range(800)]
        error_part = (
            "Traceback (most recent call last):\n"
            "  File 'core/engine.py', line 99, in compute\n"
            "ZeroDivisionError: division by zero\n"
        )
        lines.insert(400, error_part)
        huge_log = "".join(lines)

        clamped = clamp_shell_output(huge_log, max_chars=4000, tool_name="run_shell")

        self.assertIn("系统提示: 完整原始输出", clamped)
        self.assertIn("核心报错位于该文件第 401 ~", clamped)
        self.assertIn("read_file(file_path=", clamped)
        self.assertIn("ZeroDivisionError: division by zero", clamped)

    def test_read_file_outline_augmented_fallback(self):
        """方案 2 测试：验证长文件首段读取自动附带符号大纲导航，后续翻页不重复附加"""
        large_code_lines = [
            '"""模块文档注释"""',
            "class EngineManager:",
            "    def __init__(self):",
            "        self.status = 'ready'",
            "    def start_engine(self):",
            "        return True",
            "    def stop_engine(self):",
            "        return False",
            "def global_helper_calc(x, y):",
            "    return x + y",
        ]
        for i in range(210):
            large_code_lines.append(f"# line padding comment {i}")

        test_py = self.temp_path / "large_service.py"
        test_py.write_text("\n".join(large_code_lines), encoding="utf-8")

        # 1. 首次读取（start_line=1, max_lines=40）：应触发半读半纲
        res_first = read_file("large_service.py", start_line=1, max_lines=40)
        self.assertIn("大文件全貌导航·符号大纲", res_first)
        self.assertIn("EngineManager", res_first)
        self.assertIn("global_helper_calc", res_first)
        self.assertIn("定向阅读建议", res_first)

        # 2. 后续翻页读取（start_line=41, max_lines=40）：不应重复附加符号大纲
        res_next = read_file("large_service.py", start_line=41, max_lines=40)
        self.assertNotIn("大文件全貌导航·符号大纲", res_next)

    def test_stage_manager_lifecycle_and_reordering(self):
        """方案 3 测试：验证任务状态机自动驱动、Schema 优先级重排与严格掩码"""
        from core.stage_manager import StageManager, TaskStage

        schemas = default_registry.get_schemas()
        stage_mgr = StageManager(enable_stage_masking=False)

        # 1. 初始为 EXPLORE 阶段，探索工具置顶
        self.assertEqual(stage_mgr.current_stage, TaskStage.EXPLORE)
        ordered_1 = stage_mgr.reorder_or_mask_schemas(schemas)
        first_names_1 = [s["function"]["name"] for s in ordered_1[:4]]
        self.assertTrue(any(name in first_names_1 for name in ["read_file", "find_by_name", "grep_text"]))
        self.assertIn("探索排查态", stage_mgr.get_stage_banner())

        # 2. 模拟 apply_patch 成功修改代码 -> 自动迁移至 VERIFY
        stage_mgr.update_from_tool_call("apply_patch", {}, "成功应用补丁: 替换了 1 个文件。")
        self.assertEqual(stage_mgr.current_stage, TaskStage.VERIFY)
        ordered_2 = stage_mgr.reorder_or_mask_schemas(schemas)
        self.assertEqual(ordered_2[0]["function"]["name"], "run_shell")
        self.assertIn("验证闭环态", stage_mgr.get_stage_banner())

        # 3. 模拟 run_shell 测试失败 -> 自动返回 EXPLORE 阶段
        stage_mgr.update_from_tool_call("run_shell", {"command": "pytest"}, "FAILED test_core.py - AssertionError")
        self.assertEqual(stage_mgr.current_stage, TaskStage.EXPLORE)

        # 4. 验证严格掩码模式 (enable_stage_masking=True)
        stage_mgr.enable_stage_masking = True
        stage_mgr.current_stage = TaskStage.VERIFY
        masked = stage_mgr.reorder_or_mask_schemas(schemas)
        masked_names = [s["function"]["name"] for s in masked]
        self.assertIn("run_shell", masked_names)
        self.assertIn("read_file", masked_names)
        self.assertNotIn("write_file", masked_names)


if __name__ == "__main__":
    unittest.main()
