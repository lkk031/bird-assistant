"""HTTP API routes for the desktop application.

Provides SSE streaming chat, conversation management, and file export.
Replaces the Chainlit callback-based architecture with REST + SSE.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from quart import Response, request

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger
from assistant_bird.memory.context_manager import check_and_manage_context
from assistant_bird.memory.memory_manager import get_memory_manager
from assistant_bird.server.session import get_session
from assistant_bird.ui.conversations import (
    extract_title,
    load_conversations,
    load_thread_map,
    register_conversation,
    save_conversations,
    save_thread_map,
    update_conversation,
)

logger = get_logger(__name__)

USER_ID = "local_user"

AGENT_DISPLAY = {
    "supervisor": "🧠 主管",
    "general_agent": "💬 通用助手",
    "research_agent": "🔍 研究员",
    "file_ops_agent": "📁 文件操作",
    "memory_agent": "💾 记忆管理",
}


# ── SSE Helpers ──────────────────────────────────────────────────────────


def _sse_event(event: str, data: object) -> str:
    """Format a Server-Sent Events message."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_token(text: str) -> str:
    """Format a single token as an SSE event."""
    return _sse_event("token", {"text": text})


def _sse_done(**extra: object) -> str:
    """Format a done/complete SSE event."""
    return _sse_event("done", extra)


def _sse_error(error_type: str, message: str) -> str:
    """Format an error SSE event."""
    return _sse_event("error", {"type": error_type, "message": message})


# ── Streaming Core ───────────────────────────────────────────────────────


async def _stream_response(user_input: str) -> AsyncGenerator[str, None]:
    """Core streaming loop — yields SSE event strings.

    This is the heart of the migration: it ports callbacks.py:on_message
    (the astream_events loop) to SSE, replacing all cl.Message.stream_token()
    calls with _sse_token() / _sse_event() yields.
    """
    session = get_session()
    app = cast(CompiledStateGraph, session.app)

    thread_id = session.thread_id
    if thread_id is None:
        thread_id = str(uuid.uuid4())
        session.thread_id = thread_id

    # Inject memory context
    memory_mgr = get_memory_manager()
    memory_context = memory_mgr.get_context(user_input, USER_ID)

    # Context window management
    settings = get_settings()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.graph_recursion_limit,
    }

    state_override = False
    model = session.model
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
                thread_map["desktop_session"] = new_thread_id
                save_thread_map(thread_map)
                session.thread_id = new_thread_id
                thread_id = new_thread_id

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
                    "stream: context forked",
                    old_thread=old_thread_id,
                    new_thread=new_thread_id,
                    turns=user_turns,
                )

                yield _sse_event("system", {
                    "message": (
                        f"📝 对话较长（{user_turns}轮），已自动创建续接会话。\n"
                        "之前的对话已归档，可在设置中切换查看。"
                    )
                })
        except Exception as e:
            logger.warning("stream: context check failed", error=str(e))

    if not state_override:
        state = {
            "messages": [HumanMessage(content=user_input)],
            "active_agent": "supervisor",
            "user_id": USER_ID,
            "task_description": "",
            "memory_context": memory_context,
            "should_memorize": True,
        }

    current_agent = "supervisor"
    thinking_sent = False
    full_response = ""

    logger.info(
        "stream: invoking graph",
        message_length=len(user_input),
        memory_context_chars=len(memory_context),
    )

    try:
        async for event in app.astream_events(state, config, version="v2"):
            kind = event.get("event", "")
            metadata = event.get("metadata", {})
            agent_name = metadata.get("langgraph_node", "")

            # Thinking indicator
            if not thinking_sent:
                thinking_sent = True
                yield _sse_event("thinking", {"text": "💭"})

            # Agent switch detection
            if agent_name and agent_name != current_agent and agent_name in AGENT_DISPLAY:
                current_agent = agent_name
                yield _sse_event("agent_switch", {
                    "agent": agent_name,
                    "display": AGENT_DISPLAY[agent_name],
                })

            # Stream LLM tokens
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = str(chunk.content)
                    full_response += token
                    yield _sse_token(token)

            # Tool call visualization
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield _sse_event("tool_start", {
                    "name": tool_name,
                    "input": tool_input,
                })

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                tool_output = event.get("data", {}).get("output", "")
                output_str = str(tool_output)
                preview = output_str[:500]
                if len(output_str) > 500:
                    preview += "..."
                yield _sse_event("tool_end", {
                    "name": tool_name,
                    "output": preview,
                })

        yield _sse_done()
        logger.info("stream: response sent", response_length=len(full_response))

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
                logger.info("stream: conversation stored to memory")
            except Exception as e:
                logger.error("stream: memory storage failed", error=str(e))

    except RecursionError as e:
        logger.error("stream: recursion limit hit", error=str(e))
        if full_response:
            yield _sse_event("system", {
                "message": (
                    "\n\n⚠️ 任务过长已被截断。当前回复已包含部分结果，"
                    "可以换个方式继续提问。"
                )
            })
            yield _sse_done()
        else:
            yield _sse_error(
                "recursion",
                "助手执行了太多步骤还没有完成任务。建议将复杂任务拆分为多个小步骤分别提问。"
            )
    except TimeoutError as e:
        logger.error("stream: timeout", error=str(e))
        if full_response:
            yield _sse_event("system", {
                "message": "\n\n⏱️ 响应超时，已显示部分结果。可以继续追问或重试。"
            })
            yield _sse_done()
        else:
            yield _sse_error("timeout", "DeepSeek API 响应超时，请稍后重试。")
    except Exception as e:
        error_str = str(e).lower()
        logger.error("stream: failed", error=str(e))

        if "rate_limit" in error_str or "rate" in error_str:
            user_msg = "⏳ API 频率限制，请等待几秒后重试。"
        elif "connection" in error_str or "timeout" in error_str:
            user_msg = "🔌 网络连接异常，请检查网络后重试。"
        elif "recursion" in error_str:
            user_msg = "🔄 任务步骤过多，请将问题拆分为更小的步骤重试。"
        else:
            user_msg = f"❌ 处理消息时出错：{str(e)[:200]}"

        if full_response:
            yield _sse_event("system", {"message": f"\n\n⚠️ (回复中断) {user_msg}"})
            yield _sse_done()
        else:
            yield _sse_error("general", user_msg)


# ── HTTP Endpoints ───────────────────────────────────────────────────────


async def handle_chat() -> Response:
    """POST /chat — Send a message and receive a streaming response via SSE."""
    try:
        data = await request.get_json()
    except Exception:
        return Response("Invalid JSON", status=400)

    user_input = (data or {}).get("message", "")
    if not user_input or not user_input.strip():
        return Response("Empty message", status=400)

    return Response(
        _stream_response(user_input.strip()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def handle_list_conversations() -> Response:
    """GET /conversations — List all conversations as JSON."""
    session = get_session()
    convos = load_conversations()

    # Build a simple list for the frontend
    result = []
    sorted_convos = sorted(
        convos.items(),
        key=lambda kv: kv[1].get("updated_at", ""),
        reverse=True,
    )
    for tid, meta in sorted_convos:
        result.append({
            "id": tid,
            "title": meta.get("title", "未命名"),
            "updated_at": meta.get("updated_at", ""),
            "message_count": meta.get("message_count", 0),
            "archived": meta.get("archived", False),
            "continued_in": meta.get("continued_in", ""),
            "continued_from": meta.get("continued_from", ""),
        })

    return Response(
        json.dumps({"conversations": result, "active_thread_id": session.thread_id},
                   ensure_ascii=False),
        content_type="application/json",
    )


async def handle_new_conversation() -> Response:
    """POST /conversations/new — Create a new conversation."""
    session = get_session()
    new_thread_id = str(uuid.uuid4())
    session.thread_id = new_thread_id

    thread_map = load_thread_map()
    thread_map["desktop_session"] = new_thread_id
    save_thread_map(thread_map)

    register_conversation(new_thread_id)
    logger.info("api: new conversation", thread_id=new_thread_id)

    return Response(
        json.dumps({"thread_id": new_thread_id}, ensure_ascii=False),
        content_type="application/json",
    )


async def handle_switch_conversation() -> Response:
    """POST /conversations/switch — Switch to a different conversation."""
    try:
        data = await request.get_json()
    except Exception:
        return Response("Invalid JSON", status=400)

    thread_id = (data or {}).get("thread_id", "")
    if not thread_id:
        return Response("Missing thread_id", status=400)

    conversations = load_conversations()
    if thread_id not in conversations:
        return Response("Conversation not found", status=404)

    session = get_session()
    session.thread_id = thread_id

    thread_map = load_thread_map()
    thread_map["desktop_session"] = thread_id
    save_thread_map(thread_map)

    # Get conversation messages for replay
    convo = conversations[thread_id]
    logger.info("api: switched conversation", thread_id=thread_id, title=convo.get("title"))

    return Response(
        json.dumps({
            "thread_id": thread_id,
            "title": convo.get("title", "未命名"),
            "message_count": convo.get("message_count", 0),
        }, ensure_ascii=False),
        content_type="application/json",
    )


async def handle_get_messages(thread_id: str) -> Response:
    """GET /messages/{thread_id} — Get messages for a conversation (for replay)."""
    session = get_session()
    app = cast(CompiledStateGraph, session.app)

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await app.aget_state(config)
        if not state or not state.values:
            return Response(json.dumps({"messages": []}), content_type="application/json")

        raw_messages = state.values.get("messages", [])
        messages = []
        for msg in raw_messages:
            if hasattr(msg, "type"):
                role = msg.type
                content = str(msg.content) if msg.content else ""
            elif isinstance(msg, dict):
                role = msg.get("type", "")
                content = str(msg.get("content", ""))
            else:
                continue

            if not content:
                continue

            if role in ("human", "user"):
                messages.append({"role": "user", "content": content})
            elif role in ("ai", "assistant"):
                messages.append({"role": "assistant", "content": content})

        return Response(
            json.dumps({"messages": messages}, ensure_ascii=False),
            content_type="application/json",
        )
    except Exception as e:
        logger.warning("api: failed to get messages", error=str(e))
        return Response(json.dumps({"messages": []}), content_type="application/json")


async def handle_export(thread_id: str) -> Response:
    """GET /export/{thread_id} — Export a conversation as Markdown."""
    session = get_session()
    app = cast(CompiledStateGraph, session.app)

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await app.aget_state(config)
    except Exception as e:
        logger.error("export: failed to load state", error=str(e))
        return Response("Failed to load conversation", status=500)

    if not state or not state.values:
        return Response("Conversation is empty", status=404)

    raw_messages = state.values.get("messages", [])
    if not raw_messages:
        return Response("Conversation is empty", status=404)

    conversations = load_conversations()
    convo = conversations.get(thread_id, {})
    title = convo.get("title", "对话导出")
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")

    lines = [
        f"# {title}",
        "",
        f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"共 {len(raw_messages)} 条消息  |  "
        f"thread: {thread_id[:8]}",
        "",
        "---",
        "",
    ]

    for msg in raw_messages:
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
        else:
            lines.append(f"### {role}")

        lines.append("")
        lines.append(content.strip())
        lines.append("")

    markdown = "\n".join(lines)
    filename = f"conversation-{date_str}-{thread_id[:8]}.md"

    return Response(
        markdown,
        content_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
