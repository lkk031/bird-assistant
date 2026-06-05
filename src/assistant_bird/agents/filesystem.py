"""File operations agent — full local filesystem interaction with safety guards."""

import shutil
from datetime import datetime
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

FILE_OPS_SYSTEM_PROMPT = """你是鸟助手的文件操作专家。你可以全面管理本地文件系统。

## 你的能力
- 读取文件内容（read_file / read_lines）— 支持全文读取和按行范围读取
- 浏览目录结构（list_directory）
- 搜索文件（search_files）— 按 glob 模式查找
- 写入文件（write_file）— 创建新文件或覆盖已有文件
- 追加内容（append_to_file）— 在文件末尾追加内容
- 删除文件（delete_file）— 删除文件或空目录
- 移动/重命名（move_file）— 移动或重命名文件和目录
- 复制文件（copy_file）— 复制文件到新位置
- 创建目录（create_directory）— 创建多层目录
- 查看文件信息（get_file_info）— 查看大小、修改时间等元数据

## 安全规则
- 所有操作严格限制在 workspace 目录内
- 删除和覆盖操作需要用户明确确认
- 读取大文件时自动截断（5000 字符），可用 read_lines 分段读取
- 路径沙箱：任何尝试访问 workspace 外部的操作都会被拒绝

## 最佳实践
- 读取大文件时优先使用 read_lines 分段读取
- 修改文件前先用 get_file_info 确认文件状态
- 涉及多个文件操作时，先列出目录了解文件结构"""


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


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_time(timestamp: float) -> str:
    """Format a Unix timestamp to readable datetime string."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


# ============================================================================
# Read tools
# ============================================================================


@tool
def read_file(path_str: str) -> str:
    """Read the contents of a file. Path is relative to the workspace directory.

    For large files (>5000 chars), the output is truncated. Use read_lines to
    read specific line ranges instead.

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

    if path.is_dir():
        return f"Error: '{path_str}' is a directory. Use list_directory to browse it."

    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > 5000:
            remaining = len(content) - 5000
            content = content[:5000] + (
                f"\n\n...(truncated, {remaining} more chars). "
                "Use read_lines to read specific ranges."
            )
        return content
    except UnicodeDecodeError:
        return f"Error: File '{path_str}' is not a text file (binary)."
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def read_lines(path_str: str, start_line: int = 1, end_line: int = 50) -> str:
    """Read specific lines from a text file. Useful for reading large files in chunks.

    Args:
        path_str: File path, relative to workspace root.
        start_line: First line to read (1-indexed). Defaults to 1.
        end_line: Last line to read (inclusive). Defaults to 50.

    Returns:
        The requested lines with line numbers, or an error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    if not path.exists():
        return f"Error: File not found: {path_str}"

    if path.is_dir():
        return f"Error: '{path_str}' is a directory."

    if start_line < 1 or end_line < start_line:
        return (
            f"Error: Invalid line range [{start_line}:{end_line}]. "
            "start_line must be >= 1 and end_line >= start_line."
        )

    try:
        lines = path.read_text(encoding="utf-8").split("\n")
        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        result_lines = []
        for i in range(start_idx, end_idx):
            result_lines.append(f"{i + 1:>4} | {lines[i]}")

        header = f"Lines {start_idx + 1}-{end_idx} of {total_lines} in {path_str}:\n"
        if end_idx < total_lines:
            header += f"(use start_line={end_idx + 1} to continue)\n"
        return header + "\n".join(result_lines)
    except UnicodeDecodeError:
        return f"Error: File '{path_str}' is not a text file (binary)."
    except Exception as e:
        return f"Error reading file: {str(e)}"


# ============================================================================
# Directory / listing tools
# ============================================================================


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

    if not path.is_dir():
        return f"Error: '{path_str}' is not a directory."

    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        if not items:
            return f"{path_str} is empty."

        lines = [f"Contents of {path_str}:"]
        for item in items:
            if item.is_dir():
                lines.append(f"  📁 {item.name}/")
            else:
                size = item.stat().st_size
                lines.append(f"  📄 {item.name} ({_format_size(size)})")
        return "\n".join(lines)
    except PermissionError:
        return f"Error: Permission denied accessing '{path_str}'."
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def search_files(pattern: str, directory: str = ".") -> str:
    """Search for files matching a glob pattern within a directory.

    Args:
        pattern: File name pattern with wildcards (e.g., '*.py', 'test_*.py', '**/*.md').
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
            prefix = "📁" if m.is_dir() else "📄"
            size = m.stat().st_size if m.is_file() else 0
            lines.append(f"  {prefix} {rel} ({_format_size(size)})")
        if len(matches) > 50:
            lines.append(f"  ... and {len(matches) - 50} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching files: {str(e)}"


@tool
def get_file_info(path_str: str) -> str:
    """Get detailed metadata about a file or directory.

    Returns size, modification time, creation time, permissions, and type.

    Args:
        path_str: File or directory path, relative to workspace root.

    Returns:
        Formatted metadata summary, or an error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    if not path.exists():
        return f"Error: Path not found: {path_str}"

    try:
        stat = path.stat()
        info = [
            f"📋 Info for: {path_str}",
            f"   Type:        {'📁 Directory' if path.is_dir() else '📄 File'}",
            f"   Size:        {_format_size(stat.st_size)} ({stat.st_size:,} bytes)",
            f"   Created:     {_format_time(stat.st_ctime)}",
            f"   Modified:    {_format_time(stat.st_mtime)}",
            f"   Accessed:    {_format_time(stat.st_atime)}",
        ]
        if path.is_dir():
            try:
                items = list(path.iterdir())
                files = sum(1 for i in items if i.is_file())
                dirs = sum(1 for i in items if i.is_dir())
                info.append(f"   Contents:    {files} files, {dirs} subdirs")
            except PermissionError:
                info.append("   Contents:    (permission denied)")
        return "\n".join(info)
    except Exception as e:
        return f"Error getting file info: {str(e)}"


# ============================================================================
# Write / modify tools
# ============================================================================


@tool
def write_file(path_str: str, content: str, overwrite: bool = False) -> str:
    """Write content to a file. Path is relative to the workspace directory.

    By default, writing to an existing file is refused for safety.
    Set overwrite=True ONLY when the user has explicitly confirmed they want
    to overwrite the existing file.

    Args:
        path_str: File path, relative to workspace root.
        content: Text content to write to the file.
        overwrite: Set to True to overwrite an existing file. Defaults to False.

    Returns:
        Success message with file path, or error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    # Safety: warn if file exists and overwrite not set
    if path.exists() and not overwrite:
        return (
            f"⚠️ 文件 '{path_str}' 已存在。是否要覆盖？\n\n"
            f"请在对话中明确确认覆盖操作，我会使用 overwrite=True 重新执行写入。"
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        size = len(content)
        action = "覆盖写入" if (path.exists() and overwrite) else "已写入"
        logger.info("write_file: success", path=path_str, size=size, overwrite=overwrite)
        return f"✅ 文件{action}: {path_str} ({_format_size(size)})"
    except PermissionError:
        return f"Error: Permission denied writing to '{path_str}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def append_to_file(path_str: str, content: str) -> str:
    """Append content to the end of an existing file. Creates the file if it doesn't exist.

    Args:
        path_str: File path, relative to workspace root.
        content: Text content to append.

    Returns:
        Success message, or an error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
        added = len(content)
        total = path.stat().st_size
        logger.info("append_to_file: success", path=path_str, added=added, total=total)
        return (
            f"✅ 已追加 {_format_size(added)} 到文件: {path_str}"
            f"（总大小: {_format_size(total)}）"
        )
    except PermissionError:
        return f"Error: Permission denied writing to '{path_str}'."
    except Exception as e:
        return f"Error appending to file: {str(e)}"


@tool
def delete_file(path_str: str, confirm: bool = False) -> str:
    """Delete a file or an empty directory. Path is relative to the workspace.

    For safety, this requires explicit confirmation. The first call will ask
    for confirmation, and the second call with confirm=True will execute the deletion.

    Args:
        path_str: File or directory path to delete, relative to workspace root.
        confirm: Set to True to confirm deletion. Defaults to False.

    Returns:
        Success message or confirmation request.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    if not path.exists():
        return f"Error: Path not found: {path_str}"

    if not confirm:
        item_type = "目录" if path.is_dir() else "文件"
        size = ""
        if path.is_file():
            size = f" ({_format_size(path.stat().st_size)})"
        return (
            f"⚠️ 确认删除: {item_type} '{path_str}'{size}\n\n"
            f"请在对话中明确确认删除操作，我会使用 confirm=True 重新执行。"
        )

    try:
        if path.is_dir():
            path.rmdir()  # Only empty directories
        else:
            path.unlink()
        logger.info("delete_file: success", path=path_str)
        return f"✅ 已删除: {path_str}"
    except OSError as e:
        if "Directory not empty" in str(e):
            return (
                f"Error: Directory '{path_str}' is not empty. "
                f"Delete its contents first, or use list_directory to see what's inside."
            )
        return f"Error deleting '{path_str}': {str(e)}"
    except Exception as e:
        return f"Error deleting '{path_str}': {str(e)}"


# ============================================================================
# File management tools
# ============================================================================


@tool
def move_file(source: str, destination: str) -> str:
    """Move or rename a file or directory within the workspace.

    Both source and destination must be within the workspace.

    Args:
        source: Source path, relative to workspace root.
        destination: Destination path, relative to workspace root.

    Returns:
        Success message, or an error message.
    """
    try:
        src_path = _validate_path(source)
        dst_path = _validate_path(destination)
    except ValueError as e:
        return str(e)

    if not src_path.exists():
        return f"Error: Source not found: {source}"

    if dst_path.exists():
        return (
            f"⚠️ 目标 '{destination}' 已存在。\n\n"
            f"如果要覆盖，请先删除目标文件，再执行移动操作。"
        )

    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        action = "重命名" if src_path.parent == dst_path.parent else "移动"
        logger.info("move_file: success", source=source, destination=destination)
        return f"✅ {action}完成: {source} → {destination}"
    except PermissionError:
        return f"Error: Permission denied moving '{source}'."
    except Exception as e:
        return f"Error moving file: {str(e)}"


@tool
def copy_file(source: str, destination: str) -> str:
    """Copy a file to a new location within the workspace.

    Args:
        source: Source file path, relative to workspace root.
        destination: Destination file path, relative to workspace root.

    Returns:
        Success message, or an error message.
    """
    try:
        src_path = _validate_path(source)
        dst_path = _validate_path(destination)
    except ValueError as e:
        return str(e)

    if not src_path.exists():
        return f"Error: Source not found: {source}"

    if src_path.is_dir():
        return f"Error: '{source}' is a directory. copy_file only works on files."

    if dst_path.exists():
        return (
            f"⚠️ 目标 '{destination}' 已存在。\n\n"
            f"如果要覆盖，请先删除目标文件，或使用其他文件名。"
        )

    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(dst_path))
        size = dst_path.stat().st_size
        logger.info("copy_file: success", source=source, destination=destination, size=size)
        return f"✅ 复制完成: {source} → {destination} ({_format_size(size)})"
    except PermissionError:
        return f"Error: Permission denied copying '{source}'."
    except Exception as e:
        return f"Error copying file: {str(e)}"


@tool
def create_directory(path_str: str) -> str:
    """Create a new directory (and all necessary parent directories).

    Args:
        path_str: Directory path to create, relative to workspace root.

    Returns:
        Success message, or an error message.
    """
    try:
        path = _validate_path(path_str)
    except ValueError as e:
        return str(e)

    if path.exists():
        if path.is_dir():
            return f"ℹ️ 目录已存在: {path_str}"
        return f"Error: '{path_str}' already exists and is a file, not a directory."

    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.info("create_directory: success", path=path_str)
        return f"✅ 目录已创建: {path_str}"
    except PermissionError:
        return f"Error: Permission denied creating directory '{path_str}'."
    except Exception as e:
        return f"Error creating directory: {str(e)}"


# ============================================================================
# Agent factory
# ============================================================================


def create_file_ops_agent(model: BaseChatModel) -> CompiledStateGraph:
    """Create the file operations agent with all file management tools."""
    return create_react_agent(
        model=model,
        tools=[
            # Read
            read_file,
            read_lines,
            # Directory / listing
            list_directory,
            search_files,
            get_file_info,
            # Write / modify
            write_file,
            append_to_file,
            delete_file,
            # File management
            move_file,
            copy_file,
            create_directory,
        ],
        prompt=FILE_OPS_SYSTEM_PROMPT,
        name="file_ops_agent",
    )
