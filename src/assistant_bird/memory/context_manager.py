"""Context window manager — auto-summarization and thread forking.

When a conversation exceeds configured limits (turn count or token count),
this module summarizes older messages via the LLM and transparently forks
the conversation to a new LangGraph thread. The old thread is archived
but remains accessible via the conversation history dropdown.
"""

import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger
from assistant_bird.utils.token_counter import estimate_message_tokens

logger = get_logger(__name__)

SUMMARIZATION_PROMPT = """你是一个对话摘要专家。请用中文总结以下对话内容。

重点包括：
1. 用户的身份信息、偏好、习惯
2. 做出的重要决定
3. 已完成的关键任务及其结果
4. 待处理的事项或未解决的问题
5. 重要的上下文（如正在讨论的项目、文件路径、代码位置等）

简洁但全面。这段摘要将用作继续对话的唯一上下文，因此请确保所有重要信息都被保留。

对话记录：
{conversation_text}

摘要："""


async def _summarize_messages(
    model: BaseChatModel,
    messages: list[BaseMessage],
) -> str:
    """Call the LLM to produce a Chinese summary of older messages.

    Args:
        model: The DeepSeek Chat model instance.
        messages: The messages to summarize (older portion of history).

    Returns:
        A Chinese summary string, or empty string if summarization fails.
    """
    if not messages:
        return ""

    # Build a compact text representation
    parts: list[str] = []
    for m in messages:
        role = "用户" if getattr(m, "type", "") in ("human", "user") else "AI助手"
        content = m.content if hasattr(m, "content") else ""
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        text = str(content)[:1000]  # Truncate per message
        if text.strip():
            parts.append(f"[{role}]: {text}")

    conversation_text = "\n\n".join(parts)
    if not conversation_text.strip():
        return ""

    try:
        response = await model.ainvoke([
            SystemMessage(content="你是一个专业的对话摘要助手。"),
            HumanMessage(
                content=SUMMARIZATION_PROMPT.format(
                    conversation_text=conversation_text
                )
            ),
        ])
        result = str(response.content) if hasattr(response, "content") else ""
        logger.info("context_manager: summarization complete", chars=len(result))
        return result
    except Exception as e:
        logger.error("context_manager: summarization failed", error=str(e))
        return ""


async def check_and_manage_context(
    model: BaseChatModel,
    existing_messages: list[BaseMessage],
) -> tuple[list[BaseMessage], str | None, bool]:
    """Check if conversation exceeds limits and fork if needed.

    Args:
        model: The DeepSeek Chat model instance (for summarization).
        existing_messages: Current message history from the checkpointer.

    Returns:
        (seed_messages, summary_text, did_fork) — if did_fork is True,
        seed_messages contains [summary_system_msg, ...recent_messages]
        ready for the new thread. If False, the conversation stays as-is.
    """
    settings = get_settings()

    # Count user turns
    user_turns = sum(
        1 for m in existing_messages
        if hasattr(m, "type") and m.type in ("human", "user")
    )

    # Estimate token count
    estimated_tokens = estimate_message_tokens(existing_messages)

    needs_fork = (
        user_turns >= settings.context_max_turns
        or estimated_tokens >= settings.context_max_tokens
    )

    if not needs_fork or len(existing_messages) < 4:
        return [], None, False

    logger.info(
        "context_manager: threshold exceeded, forking",
        turn_count=user_turns,
        estimated_tokens=estimated_tokens,
    )

    # Split: keep recent N turns intact, summarize the rest
    keep_count = settings.context_keep_recent * 2  # user + assistant per turn
    if len(existing_messages) > keep_count:
        old_messages = list(existing_messages[:-keep_count])
        recent_messages = list(existing_messages[-keep_count:])
    else:
        # Edge case: very few messages but token-heavy → keep last 2
        old_messages = list(existing_messages[:-2])
        recent_messages = list(existing_messages[-2:])

    # Summarize old messages
    summary = ""
    if old_messages:
        summary = await _summarize_messages(model, old_messages)
        # Fallback: if summarization failed, still keep recent messages
        if not summary:
            logger.warning("context_manager: summarization returned empty, truncating")

    # Build seed messages for the new thread
    seed: list[BaseMessage] = []
    if summary:
        seed.append(SystemMessage(
            content=f"## 对话历史摘要（之前的对话太长，已自动压缩）\n\n{summary}"
        ))
    seed.extend(recent_messages)

    return seed, summary, True
