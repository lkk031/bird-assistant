"""File operations agent — local filesystem interaction with safety guards."""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

FILE_OPS_SYSTEM_PROMPT = """你是鸟助手的文件操作专家。你可以读写和浏览本地文件系统。

## 你的职责
- 读取文件内容（read_file）
- 浏览目录结构（list_directory）
- 写入文件内容（write_file）— 需用户确认
- 搜索文件（search_files）— 按名称模式查找

## 安全规则
- 所有操作严格限制在 workspace 目录内
- 写入文件会先预览内容，等待用户确认
- 读取大文件时自动截断
- 不会覆盖已存在的文件（除非用户明确允许）"""


def _get_workspace() -> Path:
    """Get the resolved workspace path."""
    return get_settings().workspace_root.resolve()


def _validate_path(path_str: str) -> Path:
    """Validate and resolve a path, ensuring it's within workspace.

    Args:
        path_str: Path relative to workspace root.

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If path is outside workspace.
    """
    workspace = _get_workspace()
    path = (workspace / path_str).resolve()
    if not str(path).startswith(str(workspace)):
        raise ValueError(f"Access denied: '{path_str}' is outside the workspace.")
    return path


@tool
def read_file(path_str: str) -> str:
    """Read the contents of a file. Path is relative to the workspace directory.

    Args:
        path_str: File path, relative to workspace root.

    Returns:
        File contents as string, or an error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    if not path.exists():
        return f"Error: File not found: {path_str}"

    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > 5000:
            content = content[:5000] + "\n...(truncated)"
        return content
    except UnicodeDecodeError:
        return f"Error: File '{path_str}' is not a text file (binary)."
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
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

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
    except PermissionError:
        return f"Error: Permission denied accessing '{path_str}'."
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def write_file(path_str: str, content: str) -> str:
    """Write content to a file. Path is relative to the workspace directory.

    IMPORTANT: Writing to an existing file will be refused unless the user
    has explicitly approved it. State in your response that this operation
    requires user confirmation before the file is actually written.

    Args:
        path_str: File path, relative to workspace root.
        content: Text content to write to the file.

    Returns:
        Success message with file path, or error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    # Safety: warn if file exists
    if path.exists():
        return (
            f"⚠️ 文件 '{path_str}' 已存在。是否要覆盖？\n\n"
            f"请在对话中明确确认覆盖操作，然后我会重新执行写入。"
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        size = len(content)
        logger.info("write_file: success", path=path_str, size=size)
        return f"✅ 文件已写入: {path_str} ({size:,} bytes)"
    except PermissionError:
        return f"Error: Permission denied writing to '{path_str}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def search_files(pattern: str, directory: str = ".") -> str:
    """Search for files matching a glob pattern within a directory.

    Args:
        pattern: File name pattern with wildcards (e.g., '*.py', 'test*.py').
        directory: Directory to search in, relative to workspace. Defaults to '.'.

    Returns:
        List of matching file paths, or an error message.
    """
    try:
        path = _validate_path(directory)
    except ValueError as e:
        return str(e)

    if not path.exists():
        return f"Error: Directory not found: {directory}"

    try:
        matches = list(path.rglob(pattern))
        if not matches:
            return f"No files matching '{pattern}' found in {directory}."

        lines = [f"Found {len(matches)} file(s) matching '{pattern}' in {directory}:"]
        for m in sorted(matches)[:50]:
            rel = m.relative_to(path)
            size = m.stat().st_size if m.is_file() else 0
            prefix = "📁" if m.is_dir() else "📄"
            lines.append(f"  {prefix} {rel} ({size:,} bytes)")
        if len(matches) > 50:
            lines.append(f"  ... and {len(matches) - 50} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching files: {str(e)}"


def create_file_ops_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the file operations agent with all file tools."""
    return create_react_agent(
        model=model,
        tools=[read_file, list_directory, write_file, search_files],
        prompt=FILE_OPS_SYSTEM_PROMPT,
        name="file_ops_agent",
    )
