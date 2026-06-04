# 🐦 鸟助手 (Assistant-Bird)

欢迎使用 **鸟助手** —— 你的个人智能 AI 助手！

## 🌟 能力总览

| 能力 | 说明 |
|------|------|
| 💬 多智能体协作 | 5 个专业 Agent，Supervisor 智能调度 |
| 🔍 网络搜索 | DuckDuckGo 实时搜索 + 网页抓取 |
| 📁 文件操作 | 读写/浏览/搜索本地文件（路径沙箱保护） |
| 🧠 长期记忆 | 三层记忆：个人事实 + 知识文档 + 对话历史 |
| 🔒 本地优先 | 数据存储在本地，API Key 仅用于 LLM 推理 |

## 💡 试试这些

- **搜索**: "帮我搜索一下 LangGraph 的最新动态"
- **抓取**: "打开 https://python.org 看看首页内容"
- **记忆**: "帮我记住：我下周五有面试"
- **回忆**: "我之前说过我有什么安排？"
- **文件**: "列出当前目录下的所有 Python 文件"
- **写作**: "帮我写一篇关于 AI Agent 发展的短文"

## 🔒 隐私说明

- 所有数据（对话历史、文档、记忆）存储在本地 `data/` 目录
- DeepSeek API 仅用于 AI 推理，Mem0 API 仅用于记忆提取
- 你可以随时查看和删除本地数据

## 📖 了解更多

- [README](https://github.com/lkk031/bird-assistant) — 架构和开发
- [CHANGELOG](CHANGELOG.md) — 开发历史
- [CONTRIBUTING](CONTRIBUTING.md) — 贡献指南
