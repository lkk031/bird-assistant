"""Suggested conversation starters for Chainlit UI."""

import chainlit as cl

STARTERS = [
    cl.Starter(
        label="🔍 帮我搜索",
        message="帮我搜索一下最近关于 AI Agent 发展的重要新闻",
        icon="search",
    ),
    cl.Starter(
        label="📝 帮我写作",
        message="请帮我写一篇关于多智能体系统的科普文章，用中文",
        icon="write",
    ),
    cl.Starter(
        label="🧠 帮我记点东西",
        message="请记住我的一些偏好：我喜欢简洁直接的答案，不喜欢啰嗦。我经常使用 Python 编程。",
        icon="brain",
    ),
    cl.Starter(
        label="📁 看看我的文件",
        message="请列出 workspace 目录下的所有文件",
        icon="folder",
    ),
]
