"""Chainlit lifecycle callbacks for the assistant.

Handles: session init (on_chat_start), message streaming (on_message),
cleanup (on_chat_end), and conversation switching (on_settings_update).
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import chainlit as cl
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from assistant_bird.config import get_settings
from assistant_bird.graph.builder import build_assistant_graph
from assistant_bird.llm.deepseek import create_deepseek_model
from assistant_bird.logging_config import get_logger
from assistant_bird.memory.context_manager import check_and_manage_context
from assistant_bird.memory.memory_manager import get_memory_manager
from assistant_bird.ui import actions  # noqa: F401 — register @cl.action_callback handlers
from assistant_bird.ui.conversations import (
    build_conversation_select,
    extract_title,
    load_conversations,
    load_thread_map,
    replay_messages,
    save_conversations,
    save_thread_map,
    update_conversation,
)
from assistant_bird.ui.starters import STARTERS

logger = get_logger(__name__)

USER_ID = "local_user"

AGENT_DISPLAY = {
    "supervisor": "🧠 主管",
    "general_agent": "💬 通用助手",
    "research_agent": "🔍 研究员",
    "file_ops_agent": "📁 文件操作",
    "memory_agent": "💾 记忆管理",
}


# ── Lifecycle: Chat Start ─────────────────────────────────────────────────


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize the assistant when a new chat session starts."""
    # Get or create a thread_id for this browser session.
    # Key = Chainlit session ID (persisted via cookie across refreshes).
    # New session → new thread. Same session → same thread.
    session_id = cl.context.session.id
    thread_map = load_thread_map()
    is_new_thread = False

    if session_id in thread_map:
        thread_id = thread_map[session_id]
        logger.info(
            "on_chat_start: reusing thread_id",
            session_id=session_id,
            thread_id=thread_id,
        )
    else:
        # Truly new session (first visit, native "New Chat" button, etc.)
        # → create a fresh thread_id. Old conversations remain accessible
        # via the settings dropdown.
        thread_id = str(uuid.uuid4())
        is_new_thread = True

        thread_map[session_id] = thread_id
        save_thread_map(thread_map)
        logger.info(
            "on_chat_start: created new thread",
            session_id=session_id,
            thread_id=thread_id,
        )

    cl.user_session.set("thread_id", thread_id)

    try:
        model = create_deepseek_model()
    except ValueError as e:
        logger.error("on_chat_start: failed to create model", error=str(e))
        await cl.Message(
            content=f"⚠️ 配置错误：{str(e)}\n\n请确保 `.env` 文件中已正确配置 API Key。"
        ).send()
        return

    cl.user_session.set("model", model)
    app = await build_assistant_graph(model)
    cl.user_session.set("app", app)

    # Replay history for existing threads
    if not is_new_thread:
        await replay_messages(app, thread_id)

    conversations = load_conversations()
    convo_meta = conversations.get(thread_id, {})
    convo_title = convo_meta.get("title", "新对话")
    convo_count = convo_meta.get("message_count", 0)

    if is_new_thread or convo_count == 0:
        await cl.Message(
            content=(
                "🐦 **鸟助手 (Assistant-Bird) 已就绪！**\n\n"
                "我的团队包括：\n"
                "🧠 **主管 Agent** — 理解意图，调度专家\n"
                "💬 **通用 Agent** — 对话、写作、推理\n"
                "🔍 **研究 Agent** — 网络搜索、信息获取\n"
                "📁 **文件 Agent** — 文件读写、目录浏览\n"
                "💾 **记忆 Agent** — 长期记忆、知识管理\n\n"
                "有什么我可以帮你的吗？"
            ),
            actions=[cl.Action(
                name="start_new_conversation",
                payload={},
                label="➕ 新对话",
                description="开始一个全新的对话",
            )],
        ).send()
    elif convo_count > 0:
        await cl.Message(
            content=(
                f"📋 **已恢复对话**: {convo_title}（{convo_count} 条消息）\n\n"
                "点击右上角 ⚙️ 可浏览和切换历史对话。"
            ),
            actions=[
                cl.Action(
                    name="start_new_conversation",
                    payload={},
                    label="➕ 新对话",
                    description="开始一个全新的对话",
                ),
                cl.Action(
                    name="export_current_conversation",
                    payload={"thread_id": thread_id},
                    label="📥 导出对话",
                    description="导出当前对话为 Markdown 文件",
                ),
            ],
        ).send()

    select_widgets = build_conversation_select(thread_id)
    await cl.ChatSettings(
        inputs=select_widgets,
        starters=STARTERS,
    ).send()


# ── Lifecycle: Message ────────────────────────────────────────────────────


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages and stream the assistant's response."""
    app = cl.user_session.get("app")
    if app is None:
        await cl.Message(content="⚠️ 助手尚未初始化，请刷新页面重试。").send()
        return

    app = cast(CompiledStateGraph, app)
    user_input = message.content

    thread_id = cl.user_session.get("thread_id")
    if thread_id is None:
        thread_id = str(uuid.uuid4())
        cl.user_session.set("thread_id", thread_id)

    # Inject memory context
    memory_mgr = get_memory_manager()
    memory_context = memory_mgr.get_context(user_input, USER_ID)

    # Context window management — auto-summarize + fork if needed
    settings = get_settings()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.graph_recursion_limit,
    }

    state_override = False
    model = cl.user_session.get("model")
    if model is not None:
        try:
            existing_state = await app.aget_state(config)
            existing_messages: list = []
            if existing_state and existing_state.values:
                existing_messages = list(existing_state.values.get("messages", []))

            seed_messages, summary, did_fork = await check_and_manage_context(
                model, existing_messages,
            )

            if did_fork:
                new_thread_id = str(uuid.uuid4())
                thread_map = load_thread_map()
                old_thread_id = thread_id
                thread_map[cl.context.session.id] = new_thread_id
                save_thread_map(thread_map)
                cl.user_session.set("thread_id", new_thread_id)
                thread_id = new_thread_id

                # Update conversation metadata: archive old, create new
                conversations = load_conversations()
                old_title = conversations.get(old_thread_id, {}).get("title", "未命名")
                if old_thread_id in conversations:
                    conversations[old_thread_id]["archived"] = True
                    conversations[old_thread_id]["continued_in"] = new_thread_id
                conversations[new_thread_id] = {
                    "title": old_title + " (续)",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "message_count": 0,
                    "continued_from": old_thread_id,
                    "summary": summary[:200] if summary else "",
                }
                save_conversations(conversations)

                seed_messages.append(HumanMessage(content=user_input))
                state = {
                    "messages": seed_messages,
                    "active_agent": "supervisor",
                    "user_id": USER_ID,
                    "task_description": "",
                    "memory_context": memory_context,
                    "should_memorize": True,
                }
                state_override = True

                config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": settings.graph_recursion_limit,
                }

                user_turns = sum(
                    1 for m in existing_messages
                    if hasattr(m, "type") and m.type in ("human", "user")
                )
                logger.info(
                    "on_message: context forked",
                    old_thread=old_thread_id,
                    new_thread=new_thread_id,
                    turns=user_turns,
                )

                await cl.Message(
                    content=(
                        f"📝 对话较长（{user_turns}轮），已自动创建续接会话。\n"
                        "之前的对话已归档，可在设置中切换查看。"
                    )
                ).send()
        except Exception as e:
            logger.warning("on_message: context check failed, continuing", error=str(e))

    if not state_override:
        state = {
            "messages": [HumanMessage(content=user_input)],
            "active_agent": "supervisor",
            "user_id": USER_ID,
            "task_description": "",
            "memory_context": memory_context,
            "should_memorize": True,
        }

    response_msg = cl.Message(content="")
    full_response = ""
    current_agent = "supervisor"
    thinking_sent = False

    logger.info(
        "on_message: invoking graph",
        message_length=len(user_input),
        memory_context_chars=len(memory_context),
    )

    try:
        async for event in app.astream_events(state, config, version="v2"):
            kind = event.get("event", "")
            metadata = event.get("metadata", {})
            agent_name = metadata.get("langgraph_node", "")

            if not thinking_sent:
                thinking_sent = True
                await response_msg.stream_token("💭 ")

            # Agent switch detection
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

            # Tool call visualization
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

        # Update conversation metadata
        if thread_id:
            conversations = load_conversations()
            convo = conversations.get(thread_id, {})
            if not convo or convo.get("title") in ("未命名", "新对话", ""):
                title = extract_title(user_input)
                if title:
                    update_conversation(thread_id, title=title)
            update_conversation(thread_id, increment_messages=True)

        # Store conversation in memory
        if full_response:
            try:
                memory_mgr.store_conversation(USER_ID, user_input, full_response)
                logger.info("on_message: conversation stored to memory")
            except Exception as e:
                logger.error("on_message: memory storage failed", error=str(e))

    except RecursionError as e:
        logger.error("on_message: recursion limit hit", error=str(e))
        if full_response:
            await response_msg.stream_token(
                "\n\n⚠️ 任务过长已被截断。当前回复已包含部分结果，"
                "可以换个方式继续提问。"
            )
            await response_msg.send()
        else:
            await cl.Message(
                content=(
                    "⚠️ 助手执行了太多步骤还没有完成任务。\n\n"
                    "建议：将复杂任务拆分为多个小步骤分别提问。"
                )
            ).send()

    except TimeoutError as e:
        logger.error("on_message: DeepSeek API timeout", error=str(e))
        if full_response:
            await response_msg.stream_token(
                "\n\n⏱️ 响应超时，已显示部分结果。可以继续追问或重试。"
            )
            await response_msg.send()
        else:
            await cl.Message(
                content="⏱️ DeepSeek API 响应超时，请稍后重试。如果持续出现，尝试缩短问题。"
            ).send()

    except Exception as e:
        error_str = str(e).lower()
        logger.error("on_message: streaming failed", error=str(e))

        if "rate_limit" in error_str or "rate" in error_str:
            user_msg = "⏳ API 频率限制，请等待几秒后重试。"
        elif "connection" in error_str or "timeout" in error_str:
            user_msg = "🔌 网络连接异常，请检查网络后重试。"
        elif "recursion" in error_str:
            user_msg = "🔄 任务步骤过多，请将问题拆分为更小的步骤重试。"
        else:
            user_msg = f"❌ 处理消息时出错：{str(e)[:200]}\n\n请重试或刷新页面。"

        if full_response:
            try:
                await response_msg.stream_token(f"\n\n⚠️ (回复中断) {user_msg}")
                await response_msg.send()
                full_response += f"\n\n⚠️ (回复中断) {user_msg}"
            except Exception:
                await cl.Message(content=user_msg).send()
        else:
            await cl.Message(content=user_msg).send()


# ── Lifecycle: Chat End ───────────────────────────────────────────────────


@cl.on_chat_end
async def on_chat_end() -> None:
    """Clean up when the chat session ends."""
    logger.info("on_chat_end: session ended")


# ── Settings: Conversation Switching ──────────────────────────────────────


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Handle ChatSettings changes — conversation switching."""
    selected = settings.get("conversation_switch", "")
    if not selected or selected == "__none__":
        return

    conversations = load_conversations()
    if selected not in conversations:
        logger.warning(
            "on_settings_update: invalid selection, ignoring",
            selected=selected,
        )
        return

    session_id = cl.context.session.id
    current_thread = cl.user_session.get("thread_id")

    if selected == current_thread:
        return

    convo = conversations.get(selected, {})
    title = convo.get("title", "未命名")
    count = convo.get("message_count", 0)

    thread_map = load_thread_map()
    thread_map[session_id] = selected
    save_thread_map(thread_map)
    cl.user_session.set("thread_id", selected)

    logger.info(
        "on_settings_update: switched conversation",
        session_id=session_id,
        thread_id=selected,
        title=title,
    )

    await cl.Message(
        content=(
            f"📋 **已切换到**: {title}（{count} 条消息）\n\n"
            "发送任意消息即可继续此对话。\n"
            "💡 如需查看历史记录，刷新页面即可。"
        )
    ).send()
