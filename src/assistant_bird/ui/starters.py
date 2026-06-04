"""Suggested conversation starters for Chainlit UI."""

import chainlit as cl

STARTERS = [
    cl.Starter(
        label="🌤️ 今日天气与新闻",
        message="今天天气如何？有什么重要的新闻吗？",
        icon="weather",
    ),
    cl.Starter(
        label="📝 帮我写点东西",
        message="请帮我写一篇关于人工智能发展的简短文章",
        icon="write",
    ),
    cl.Starter(
        label="💡 解释一个概念",
        message="请用简单的话解释一下什么是 LangGraph 多智能体系统",
        icon="idea",
    ),
    cl.Starter(
        label="🌐 搜索网络信息",
        message="帮我搜索一下最近关于 DeepSeek 的最新消息（注意：搜索功能即将上线）",
        icon="search",
    ),
]
