# -*- coding: utf-8 -*-
"""
tools/framework/workspace.py: 动态工作区感知与沙箱根目录管理
支持优先级：显式注入/命令行指定 (--cwd) > 终端向上探测的 .git 根目录 > Path.cwd()
"""
import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Union

class WorkspaceContext:
    """
    工作区上下文对象：管理 Agent 当前操作的目标工程根目录，
    杜绝将工作区死锁在 Agent 源码自身的安装目录。
    """
    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        self._root: Optional[Path] = None
        if root_dir:
            self.set_root(root_dir)

    def _detect_git_root(self, start_dir: Optional[Path] = None) -> Optional[Path]:
        """探测指定目录或当前目录所在的 git 根目录"""
        try:
            cwd = str(start_dir or Path.cwd())
            res = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            if res:
                p = Path(res).resolve()
                if p.exists() and p.is_dir():
                    return p
        except Exception:
            pass
        return None

    def _detect_default_root(self) -> Path:
        """自动推断默认工作区根目录"""
        # 1. 优先探测当前终端所在目录的 git 根目录
        git_root = self._detect_git_root()
        if git_root:
            return git_root
        # 2. 降级为当前终端物理工作目录 (若处于打包内置目录则重定向至用户工程区)
        p = Path.cwd().resolve()
        if p.name.lower() in ("super-server", "bin", "resources", "_internal"):
            user_proj = Path.home() / "super-harnes"
            if user_proj.exists():
                return user_proj
            user_ws = Path.home() / ".super-harnes" / "workspace"
            user_ws.mkdir(parents=True, exist_ok=True)
            return user_ws
        return p

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = self._detect_default_root()
        return self._root

    def set_root(self, root_dir: Union[str, Path]) -> Path:
        """显式重定向当前工作区根目录"""
        p = Path(root_dir).resolve()
        if not p.exists():
            raise FileNotFoundError(f"指定的工作区路径不存在: {root_dir}")
        if not p.is_dir():
            raise NotADirectoryError(f"指定的工作区路径不是有效目录: {root_dir}")
        self._root = p
        return self._root

    def reset_to_default(self) -> Path:
        """重置回自动探测的默认工作区根目录"""
        self._root = None
        return self.root

    def resolve_path(self, path_str: Union[str, Path]) -> Path:
        """将相对路径或绝对路径解析为基于当前工作区根目录的绝对路径"""
        p = Path(path_str)
        if not p.is_absolute():
            return (self.root / p).resolve()
        return p.resolve()

    def is_inside(self, path: Union[str, Path]) -> bool:
        """校验目标路径是否严格限制在当前工作区内"""
        resolved = self.resolve_path(path)
        try:
            resolved.relative_to(self.root)
            return True
        except ValueError:
            return False

    def relative_path(self, path: Union[str, Path]) -> str:
        """返回相对工作区根目录的规范 POSIX 路径"""
        resolved = self.resolve_path(path)
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError:
            return str(resolved)

# 全局单例
default_workspace = WorkspaceContext()

def get_workspace_root() -> Path:
    return default_workspace.root

def set_workspace_root(root_dir: Union[str, Path]) -> Path:
    return default_workspace.set_root(root_dir)

def atomic_write_text(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
    """
    原子写入文本文件，杜绝写入中断导致原文件损坏或截断：
    1. 确保目标父目录已创建；
    2. 在同级目录创建带 PID 与随机数的临时文件（同目录保证在同一文件系统卷，使 os.replace 为原子操作）；
    3. 写入内容，调用 f.flush() 与 os.fsync(f.fileno()) 强制刷盘；
    4. 使用 os.replace 进行内核级原子重命名替换目标文件；
    5. 若抛出任何异常，在 finally 中安全清理临时文件，保证原文件完好无损。
    """
    target = Path(path)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    tmp_file = parent / f".tmp_{target.name}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp_file, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # Windows 环境防杀软/IDE 瞬态文件锁微重试
        for attempt in range(3):
            try:
                os.replace(tmp_file, target)
                break
            except (PermissionError, OSError):
                if attempt < 2 and sys.platform == "win32":
                    import time
                    time.sleep(0.03 * (attempt + 1))
                    continue
                raise
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass

def is_binary_file(file_path: Union[str, Path]) -> bool:
    """快速探测是否为二进制文件（排除带有标准文本 BOM 的 UTF-16/UTF-8 编码文件）"""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if not chunk:
                return False
            # 排除带有标准文本 BOM 的 UTF-16/UTF-8 编码文本
            if chunk.startswith(b"\xff\xfe") or chunk.startswith(b"\xfe\xff") or chunk.startswith(b"\xef\xbb\xbf"):
                return False
            return b"\x00" in chunk
    except Exception:
        return True

def detect_file_encoding(file_path: Union[str, Path]) -> str:
    """探测文件文本编码（支持带 BOM 的 UTF-16 LE/BE, UTF-8-SIG，默认回退 utf-8）"""
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
            if header.startswith(b"\xff\xfe") or header.startswith(b"\xfe\xff"):
                return "utf-16"
            elif header.startswith(b"\xef\xbb\xbf"):
                return "utf-8-sig"
    except Exception:
        pass
    return "utf-8"

