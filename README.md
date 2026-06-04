# 🐦 鸟助手 (Assistant-Bird)

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-4%2F5-orange)]()
[![Tests](https://img.shields.io/badge/tests-30%20passed-brightgreen)]()

一个基于 LangGraph 多智能体框架的开源个人 AI 助手，具备多智能体协作、长期记忆、Web 搜索与抓取、文件操作等能力。

## ✨ 特性

| 特性 | 说明 | 状态 |
|------|------|------|
| 💬 多智能体协作 | Supervisor 模式，5 个专业 Agent 协同 | ✅ |
| 🔍 网络搜索 | DuckDuckGo 实时搜索 | ✅ |
| 📄 网页抓取 | httpx + BeautifulSoup 内容提取 | ✅ |
| 📁 文件操作 | 读写/浏览/搜索，路径沙箱保护 | ✅ |
| 🧠 长期记忆 | Mem0 个人事实 + Chroma 文档 + SQLite 历史 | ✅ |
| 🖥️ Web 界面 | Chainlit 流式聊天，Agent 切换显示 | ✅ |
| 🔒 本地优先 | 数据存储在本地，API Key 仅用于 LLM 推理 | ✅ |
| 🧪 测试覆盖 | 30 个测试覆盖工具/记忆/安全 | ✅ |

## 🚀 快速开始

### 前提

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- [DeepSeek API Key](https://platform.deepseek.com/)（免费注册）
- Mem0 API Key（可选，用于长期记忆功能）

### 安装

```bash
git clone https://github.com/lkk031/bird-assistant.git
cd bird-assistant

cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY

poetry install
poetry run assistant-bird
```

浏览器打开 **http://localhost:8000**。

### 可选配置

```bash
# .env 中的可选配置
MEM0_API_KEY=your_key      # 开启长期记忆（推荐）
WORKSPACE_ROOT=./workspace  # 文件操作根目录
LOG_LEVEL=INFO              # DEBUG / INFO / WARNING
```

## 🏗️ 架构

```
┌─────────────────────────────────────────┐
│              Chainlit Web UI             │
│        (流式输出 · Agent 显示 · 工具可视化)  │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────▼──────────────┐
    │     🧠 Supervisor Agent     │
    │    (langgraph-supervisor)   │
    │    意图理解 · 任务委派 · 结果综合 │
    └──┬────────┬────────┬───────┘
       │        │        │
  ┌────▼───┐┌──▼────┐┌──▼──────┐┌──▼──────┐
  │💬通用  ││🔍研究 ││📁文件   ││💾记忆   │
  │ Agent  ││ Agent ││ Agent   ││ Agent   │
  │无工具  ││3工具  ││4工具    ││4工具    │
  └────────┘└───────┘└─────────┘└─────────┘

┌──────────────────────────────────────────┐
│             Memory System                │
│  Mem0 (个人事实) · Chroma (文档) · SQLite (历史) │
└──────────────────────────────────────────┘
```

### Agent 详细

| Agent | 工具 | 擅长 |
|-------|------|------|
| **Supervisor** | handoff（自动生成） | 理解意图、委派任务 |
| **General** | 无 | 对话、写作、推理、翻译、总结 |
| **Research** | web_search, scrape_webpage, search_and_scrape | 网络搜索、信息核查、网页抓取 |
| **File Ops** | read_file, list_directory, write_file, search_files | 文件读写、目录浏览、路径沙箱 |
| **Memory** | recall_memories, remember_fact, search_documents, list_facts | 长期记忆、知识库搜索 |

### 记忆数据流

```
每轮对话:
1. 用户输入 → 并行搜索 Mem0 + Chroma + SQLite
2. 记忆上下文注入 Supervisor 决策
3. Agent 执行任务 → 流式返回
4. 异步存储: SQLite 记录 + Mem0 提取事实
```

## 📂 项目结构

```
src/assistant_bird/
├── main.py              # Chainlit 入口
├── config.py            # pydantic-settings 配置
├── logging_config.py    # structlog 日志
├── llm/deepseek.py      # ChatDeepSeek 工厂
├── graph/               # LangGraph 图定义
│   ├── state.py         # AssistantState
│   ├── builder.py       # Supervisor 图组装
│   └── checkpointer.py  # InMemorySaver
├── agents/              # 5 个 Agent 定义
│   ├── supervisor.py    # 主管
│   ├── general.py       # 通用对话
│   ├── research.py      # 研究搜索
│   ├── filesystem.py    # 文件操作
│   └── memory_agent.py  # 记忆管理
├── tools/               # 工具实现
│   ├── registry.py      # 工具注册中心
│   ├── web_search.py    # DuckDuckGo 搜索
│   └── web_scraper.py   # 网页抓取
├── memory/              # 记忆系统
│   ├── memory_manager.py # 编排器
│   ├── mem0_client.py    # Mem0 API
│   ├── vector_store.py   # Chroma 向量库
│   └── conversation_db.py # SQLite 历史
└── ui/                  # Chainlit 界面
    ├── callbacks.py     # 生命周期
    ├── starters.py      # 对话入口
    └── renderers.py     # 自定义渲染
```

## 🛠️ 开发

```bash
# 开发模式（热重载）
poetry run chainlit run src/assistant_bird/main.py -w

# 测试
poetry run pytest                 # 全部
poetry run pytest -k "memory"     # 按关键字
poetry run pytest -v              # 详细输出

# 代码质量
poetry run ruff check src/ tests/  # Lint
poetry run ruff check --fix .      # 自动修复
poetry run mypy src/               # 类型检查
```

## 🤝 贡献

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- 🐛 Bug 报告 → [Issues](https://github.com/lkk031/bird-assistant/issues)
- 💡 功能建议 → [Discussions](https://github.com/lkk031/bird-assistant/discussions)
- 📖 开发记录 → [CHANGELOG.md](CHANGELOG.md)
- 🤖 Claude Code 指南 → [CLAUDE.md](CLAUDE.md)

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)。
