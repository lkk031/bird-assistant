"""Chainlit Action callbacks for conversation management.

These are registered globally by Chainlit when this module is imported.
"""

import uuid
from datetime import datetime
from typing import cast

import chainlit as cl
from langgraph.graph.state import CompiledStateGraph

from assistant_bird.logging_config import get_logger
from assistant_bird.ui.conversations import (
    build_conversation_select,
    load_conversations,
    load_thread_map,
    register_conversation,
    save_thread_map,
)
from assistant_bird.ui.starters import STARTERS

logger = get_logger(__name__)


@cl.action_callback("export_current_conversation")
async def on_export_conversation(action: cl.Action) -> None:
    """Export the current conversation as a downloadable Markdown file."""
    thread_id = cl.user_session.get("thread_id")
    app = cl.user_session.get("app")

    if not thread_id or not app:
        await cl.Message(content="⚠️ 无法导出：对话尚未初始化。").send()
        return

    app = cast(CompiledStateGraph, app)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await app.aget_state(config)
    except Exception as e:
        logger.error("export: failed to load state", error=str(e))
        await cl.Message(content="⚠️ 加载对话失败，请稍后重试。").send()
        return

    if not state or not state.values:
        await cl.Message(content="⚠️ 当前对话无内容可导出。").send()
        return

    messages = state.values.get("messages", [])
    if not messages:
        await cl.Message(content="⚠️ 当前对话无内容可导出。").send()
        return

    conversations = load_conversations()
    convo = conversations.get(thread_id, {})
    title = convo.get("title", "对话导出")
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")

    lines = [
        f"# {title}",
        "",
        f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"共 {len(messages)} 条消息  |  "
        f"thread: {thread_id[:8]}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role = getattr(msg, "type", "")
        content = str(getattr(msg, "content", ""))

        if role in ("human", "user"):
            lines.append("### 🧑 用户")
        elif role in ("ai", "assistant"):
            lines.append("### 🤖 鸟助手")
        elif role == "tool":
            tool_name = getattr(msg, "name", "")
            label = f"工具: {tool_name}" if tool_name else "工具"
            lines.append(f"### 🔧 {label}")
        elif role == "system":
            lines.append("### ⚙️ 系统")
        else:
            lines.append(f"### {role}")

        lines.append("")
        lines.append(content.strip())
        lines.append("")

    markdown = "\n".join(lines)
    filename = f"conversation-{date_str}-{thread_id[:8]}.md"

    await cl.Message(
        content="📥 对话已导出",
        elements=[
            cl.File(
                name=filename,
                content=markdown.encode("utf-8"),
                display="inline",
                mime="text/markdown",
            )
        ],
    ).send()

    logger.info(
        "export: conversation exported",
        thread_id=thread_id,
        message_count=len(messages),
        file_size=len(markdown),
    )


@cl.action_callback("start_new_conversation")
async def on_start_new_conversation(action: cl.Action) -> None:
    """Start a fresh conversation by creating a new thread_id."""
    new_thread_id = str(uuid.uuid4())
    thread_map = load_thread_map()

    session_id = cl.context.session.id
    thread_map[session_id] = new_thread_id
    save_thread_map(thread_map)

    cl.user_session.set("thread_id", new_thread_id)

    # Register immediately so it appears in the dropdown
    register_conversation(new_thread_id)

    # Refresh the conversation selector and starters
    select_widgets = build_conversation_select(new_thread_id)
    await cl.ChatSettings(inputs=select_widgets, starters=STARTERS).send()

    logger.info(
        "action: new conversation created",
        session_id=session_id,
        thread_id=new_thread_id,
    )

    # Signal the browser to reload for a clean conversation window
    await cl.send_window_message({"type": "assistant_bird_new_conversation"})
