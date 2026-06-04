"""File operations agent — local filesystem interaction."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.config import get_settings

FILE_OPS_SYSTEM_PROMPT = """你是鸟助手的文件操作专家。你可以读取和浏览本地文件系统。

## 你的职责
- 读取文件内容
- 浏览目录结构
- 搜索文件

## 安全规则
- 所有操作限制在 workspace 目录内
- 写操作需要用户确认（未来功能）
- 读取大文件时自动截断"""


def _get_workspace() -> Path:
    """Get the resolved workspace path."""
    settings = get_settings()
    return settings.workspace_root.resolve()


@tool
def read_file(path_str: str) -> str:
    """Read the contents of a file. Path is relative to the workspace directory.

    Args:
        path_str: File path, relative to workspace root.

    Returns:
        File contents as string, or an error message.
    """
    workspace = _get_workspace()
    path = (workspace / path_str).resolve()

    if not str(path).startswith(str(workspace)):
        return "Error: Access denied — path is outside workspace."

    if not path.exists():
        return f"Error: File not found: {path_str}"

    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > 5000:
            content = content[:5000] + "\n...(truncated)"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_directory(path_str: str = ".") -> str:
    """List the contents of a directory. Path is relative to the workspace.

    Args:
        path_str: Directory path, relative to workspace root. Defaults to '.'.

    Returns:
        Formatted directory listing, or an error message.
    """
    workspace = _get_workspace()
    path = (workspace / path_str).resolve()

    if not str(path).startswith(str(workspace)):
        return "Error: Access denied — path is outside workspace."

    if not path.exists():
        return f"Error: Directory not found: {path_str}"

    try:
        items = sorted(path.iterdir())
        if not items:
            return f"{path_str} is empty."

        lines = [f"Contents of {path_str}:"]
        for item in items:
            if item.is_dir():
                lines.append(f"  📁 {item.name}/")
            else:
                size = item.stat().st_size
                lines.append(f"  📄 {item.name} ({size:,} bytes)")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def create_file_ops_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the file operations agent with file tools."""
    return create_react_agent(
        model=model,
        tools=[read_file, list_directory],
        prompt=FILE_OPS_SYSTEM_PROMPT,
        name="file_ops_agent",
    )
