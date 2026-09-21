# -*- coding: utf-8 -*-
"""
scripts/run_checks.py: 快速自检与自动化测试启动脚本
"""
import sys
import unittest
from pathlib import Path

# 将项目根目录置入 sys.path 顶层
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main():
    print("=== 正在运行自动化测试套件 ===")
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
