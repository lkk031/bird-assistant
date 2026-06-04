"""Chainlit lifecycle callbacks for the assistant."""

from typing import cast

import chainlit as cl
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from assistant_bird.graph.builder import build_assistant_graph
from assistant_bird.llm.deepseek import create_deepseek_model
from assistant_bird.logging_config import get_logger
from assistant_bird.ui.starters import STARTERS

logger = get_logger(__name__)

# Agent display names for UI
AGENT_DISPLAY = {
    "supervisor": "🧠 主管",
    "general_agent": "💬 通用助手",
    "research_agent": "🔍 研究员",
    "file_ops_agent": "📁 文件操作",
    "memory_agent": "💾 记忆管理",
}


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize the assistant when a new chat session starts."""
    logger.info("on_chat_start: new chat session")

    try:
        model = create_deepseek_model()
    except ValueError as e:
        logger.error("on_chat_start: failed to create model", error=str(e))
        await cl.Message(
            content=f"⚠️ 配置错误：{str(e)}\n\n请确保 `.env` 文件中已正确配置 API Key。"
        ).send()
        return

    app = build_assistant_graph(model)
    cl.user_session.set("app", app)

    await cl.Message(
        content=(
            "🐦 **鸟助手 (Assistant-Bird) 已就绪！**\n\n"
            "我现在拥有了 **多智能体协作** 能力，我的团队包括：\n"
            "🧠 **主管 Agent** — 理解意图，调度专家\n"
            "💬 **通用 Agent** — 对话、写作、推理\n"
            "🔍 **研究 Agent** — 网络搜索、信息获取\n"
            "📁 **文件 Agent** — 文件读写、目录浏览\n"
            "💾 **记忆 Agent** — 记住偏好（开发中）\n\n"
            "有什么我可以帮你的吗？"
        )
    ).send()

    await cl.ChatSettings(starters=STARTERS).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages and stream the assistant's response."""
    app = cl.user_session.get("app")
    if app is None:
        await cl.Message(content="⚠️ 助手尚未初始化，请刷新页面重试。").send()
        return

    app = cast(CompiledStateGraph, app)

    state = {
        "messages": [HumanMessage(content=message.content)],
        "active_agent": "supervisor",
        "user_id": "local_user",
        "task_description": "",
        "memory_context": "",
        "should_memorize": False,
    }

    config = {"configurable": {"thread_id": "local_user"}}

    response_msg = cl.Message(content="")
    full_response = ""
    current_agent = "supervisor"

    logger.info("on_message: invoking graph", message_length=len(message.content))

    try:
        async for event in app.astream_events(state, config, version="v2"):
            kind = event.get("event", "")
            metadata = event.get("metadata", {})
            agent_name = metadata.get("langgraph_node", "")

            # Detect agent switches and show a marker
            if agent_name and agent_name != current_agent and agent_name in AGENT_DISPLAY:
                current_agent = agent_name
                await response_msg.stream_token(
                    f"\n\n**[{AGENT_DISPLAY[agent_name]}]**\n"
                )

            # Stream LLM tokens
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = str(chunk.content)
                    full_response += token
                    await response_msg.stream_token(token)

            # Show tool calls
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                await response_msg.stream_token(
                    f"\n🔧 调用工具: **{tool_name}**\n"
                )

            elif kind == "on_tool_end":
                tool_output = event.get("data", {}).get("output", "")
                if tool_output:
                    preview = str(tool_output)[:300]
                    if len(str(tool_output)) > 300:
                        preview += "..."
                    await response_msg.stream_token(f"📋 结果:\n{preview}\n")

        await response_msg.send()
        logger.info("on_message: response sent", response_length=len(full_response))

    except Exception as e:
        logger.error("on_message: streaming failed", error=str(e))
        await cl.Message(
            content=(
                f"❌ 处理消息时出错：{str(e)}\n\n"
                "请检查网络连接和 API 配置后重试。"
            )
        ).send()


@cl.on_chat_end
async def on_chat_end() -> None:
    """Clean up when the chat session ends."""
    logger.info("on_chat_end: session ended")
