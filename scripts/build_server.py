import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

root = Path(__file__).resolve().parent.parent
print(f"Building super-server from root: {root}")

excludes = [
    "torch", "torchvision", "torchaudio",
    "transformers", "scipy", "pandas", "sklearn", "scikit_learn",
    "sentence_transformers", "safetensors", "accelerate", "datasets",
    "sympy", "openpyxl", "celery", "redis", "pymilvus", "fitz", "pymupdf",
    "matplotlib", "pyarrow", "lxml", "kombu", "billiard", "amqp",
    "alembic", "SQLAlchemy", "psycopg", "psycopg2", "PyMySQL",
    "minio", "ir_datasets", "FlagEmbedding", "peft", "dill",
    "tkinter", "IPython", "notebook"
]

exclude_args = [f"--exclude-module={mod}" for mod in excludes]

dist_dir = root / "desktop" / "bin"
build_dir = root / "build_server"

dist_dir.mkdir(parents=True, exist_ok=True)

args = [
    str(root / "server" / "run_server.py"),
    "--name=super-server",
    "--onedir",
    "--noconfirm",
    "--clean",
    f"--paths={str(root)}",
    f"--add-data={str(root / 'config')};config",
    f"--add-data={str(root / 'mcp' / 'servers')};mcp/servers",
    f"--add-data={str(root / '.skills')};.skills",
    "--hidden-import=uvicorn",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols",
    "--hidden-import=uvicorn.protocols.http",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=uvicorn.lifespan",
    "--hidden-import=uvicorn.lifespan.on",
    "--hidden-import=uvicorn.lifespan.off",
    "--hidden-import=fastapi",
    "--hidden-import=starlette",
    "--hidden-import=starlette.responses",
    "--hidden-import=starlette.routing",
    "--hidden-import=starlette.middleware",
    "--hidden-import=pydantic",
    "--hidden-import=openai",
    "--hidden-import=dotenv",
    "--hidden-import=prompt_toolkit",
    "--hidden-import=tools",
    "--hidden-import=tools.framework",
    "--hidden-import=tools.framework.registry",
    "--hidden-import=tools.framework.executor",
    "--hidden-import=tools.framework.policies",
    "--hidden-import=tools.framework.workspace",
    "--hidden-import=tools.framework.snapshot",
    "--hidden-import=tools.builtin",
    "--hidden-import=tools.builtin.file_tools",
    "--hidden-import=tools.builtin.patch_tool",
    "--hidden-import=tools.builtin.search_tools",
    "--hidden-import=tools.builtin.shell_tool",
    "--hidden-import=tools.builtin.skill_tools",
    "--hidden-import=core.agent",
    "--hidden-import=core.session",
    "--hidden-import=core.loop_detector",
    "--hidden-import=core.stage_manager",
    "--hidden-import=core.prompt",
    "--hidden-import=context",
    "--hidden-import=skills",
    "--hidden-import=mcp",
    f"--distpath={str(dist_dir)}",
    f"--workpath={str(build_dir)}",
    f"--specpath={str(build_dir)}"
] + exclude_args

print("Starting PyInstaller compilation...")
PyInstaller.__main__.run(args)
print(f"Build completed successfully in {dist_dir}!")
