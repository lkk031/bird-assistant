# 🐦 鸟助手 (Assistant-Bird)

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-30%20passed-brightgreen)]()

一个基于 LangGraph 多智能体框架的开源个人 AI 助手，具备多智能体协作、长期记忆、Web 搜索与抓取、文件操作等能力。**现已支持原生桌面窗口**（不再需要浏览器）。

## ✨ 特性

| 特性 | 说明 | 状态 |
|------|------|------|
| 🖥️ 原生桌面 | pywebview 桌面窗口，独立于浏览器 | ✅ |
| 💬 多智能体协作 | Supervisor 模式，5 个专业 Agent 协同 | ✅ |
| 🔍 网络搜索 | DuckDuckGo 实时搜索 | ✅ |
| 📄 网页抓取 | httpx + BeautifulSoup 内容提取 | ✅ |
| 📁 文件操作 | 读写/浏览/搜索，路径沙箱保护 | ✅ |
| 🧠 长期记忆 | Mem0 个人事实 + Chroma 文档 + SQLite 历史 | ✅ |
| 🔒 本地优先 | 数据存储在本地，API Key 仅用于 LLM 推理 | ✅ |
| 🧪 测试覆盖 | 30 个测试覆盖工具/记忆/安全 | ✅ |

### 🧰 内置功能

| 功能 | 命令示例 | 说明 |
|------|---------|------|
| 🔥 **GitHub 热点** | 「GitHub 今天最火的 Python 项目」 | 按语言 + 时间范围查看趋势仓库 |
| 📰 **全球新闻** | 「今天有什么大事」「科技新闻」 | 多源聚合（Google/BBC/Guardian 等），支持地区/话题 |
| 📖 **文章详情** | 「这篇新闻讲了什么」 | 按标题查找可跳转链接和摘要 |
| 🌤️ **天气查询** | 「北京今天天气怎么样」 | 全球城市实时天气 + 7 日预报 |
| 🔍 **网页搜索** | 「搜索 XXX」 | DuckDuckGo 实时搜索 |
| 📄 **网页抓取** | 「帮我总结这个链接」 | 自动提取网页正文内容 |
| 📁 **文件管理** | 「列出 workspace 的文件」「帮我写一个 notes.txt」 | 文件全生命周期管理（读写/追加/复制/移动/删除/目录） |

## 🚀 快速开始

### 前提

- Python 3.12+ （推荐系统 Python，见下方平台说明）
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
```

### 启动

```bash
# 桌面窗口模式（默认）
poetry run assistant-bird

# 浏览器开发模式（调试用）
poetry run assistant-bird --dev
```

桌面模式下会打开原生系统窗口；`--dev` 模式在浏览器中打开 `http://localhost:19900`。

### 可选配置

```bash
# .env 中的可选配置
MEM0_API_KEY=your_key      # 开启长期记忆（推荐）
WORKSPACE_ROOT=./workspace  # 文件操作根目录
LOG_LEVEL=INFO              # DEBUG / INFO / WARNING
```

## 🖥️ 桌面启动器

### Linux（系统菜单 / 桌面图标）

已内置 `.desktop` 文件，安装后可在系统菜单中搜索"鸟助手"一键启动：

```bash
cp desktop/assistant-bird.desktop ~/.local/share/applications/
cp desktop/assistant-bird.svg ~/.local/share/icons/
update-desktop-database ~/.local/share/applications/
```

> **注意**：如果 Poetry 虚拟环境路径不同，请修改 `.desktop` 文件中的 `Exec=` 行，指向你的 `poetry run assistant-bird` 实际路径。或者用以下包装脚本：

```bash
# 创建一个启动脚本 ~/.local/bin/assistant-bird
#!/bin/bash
cd /path/to/bird-assistant && poetry run assistant-bird
```

### Windows

Windows 不支持 `.desktop` 文件，推荐以下方式之一：

**方式一：快捷方式（推荐）**

1. 右键桌面 → 新建 → 快捷方式
2. 位置填入以下命令（替换路径）：
   ```
   C:\Windows\System32\cmd.exe /c "cd /d C:\path\to\bird-assistant && poetry run assistant-bird"
   ```
3. 下一步 → 命名为"鸟助手" → 完成
4. 右键快捷方式 → 属性 → 更改图标（可选）

**方式二：PowerShell 启动脚本**

创建 `launch.ps1`（在项目根目录）：

```powershell
Set-Location $PSScriptRoot
poetry run assistant-bird
```

双击 `launch.ps1` 即可启动（首次可能需要 `Set-ExecutionPolicy RemoteSigned`）。

**方式三：开始菜单**（手动）

将上述快捷方式复制到 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\` 即可在开始菜单搜索到。

### macOS

**方式一：Automator 应用（推荐）**

1. 打开 `Automator` → 新建"应用程序"
2. 添加"运行 Shell 脚本"操作
3. 填入：
   ```bash
   cd /path/to/bird-assistant && /usr/local/bin/poetry run assistant-bird
   ```
4. 文件 → 存储为"鸟助手.app" → 拖到 Dock 或桌面

**方式二：终端别名**

在 `~/.zshrc` 中添加：
```bash
alias assistant-bird='cd /path/to/bird-assistant && poetry run assistant-bird'
```

---

## 🏗️ 架构

```
┌── Desktop Window (pywebview) ────────────────────────────┐
│  HTML/CSS/JS 聊天前端（SSE 流式 / Agent 切换 / 工具卡片）   │
│  ↕ HTTP localhost:19900                                  │
├──────────────────────────────────────────────────────────┤
│  Quart ASGI Server（路由 / 会话 / SSE）                    │
│  ↕  astream_events(v2)                                  │
├──────────────────────────────────────────────────────────┤
│           🧠 Supervisor Agent                            │
│         意图理解 · 任务委派 · 结果综合                       │
├──────────┬──────────┬───────────┬───────────┤
│ 💬 通用  │ 🔍 研究  │ 📁 文件   │ 💾 记忆  │
│ Agent   │ Agent    │ Agent     │ Agent    │
│ 无工具   │ 10 工具  │ 11 工具   │ 4 工具   │
└──────────┴──────────┴───────────┴───────────┘

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
| **Research** | web_search, scrape_webpage, search_and_scrape, github_trending, world_news, read_news_article, get_weather | 网络搜索、信息核查、网页抓取、热点追踪、新闻速览、天气查询 |
| **File Ops** | read_file, read_lines, list_directory, search_files, get_file_info, write_file, append_to_file, delete_file, move_file, copy_file, create_directory | 文件全生命周期管理、路径沙箱 |
| **Memory** | recall_memories, remember_fact, search_documents, list_facts | 长期记忆、知识库搜索 |

### 记忆数据流

```
每轮对话:
1. 用户输入 → 并行搜索 Mem0 + Chroma + SQLite
2. 记忆上下文注入 Supervisor 决策
3. Agent 执行任务 → SSE 流式返回
4. 异步存储: SQLite 记录 + Mem0 提取事实
```

## 📂 项目结构

```
src/assistant_bird/
├── main.py              # CLI 入口
├── config.py            # pydantic-settings 配置
├── app_dir.py           # 跨平台应用数据目录
├── logging_config.py    # structlog 日志
├── llm/deepseek.py      # ChatDeepSeek 工厂
├── graph/               # LangGraph 图定义
│   ├── state.py         # AssistantState
│   ├── builder.py       # Supervisor 图组装
│   └── checkpointer.py  # AsyncSqliteSaver
├── agents/              # 5 个 Agent 定义
│   ├── supervisor.py
│   ├── general.py
│   ├── research.py
│   ├── filesystem.py
│   └── memory_agent.py
├── tools/               # 工具注册中心 + 内置工具
│   ├── registry.py
│   ├── web_search.py
│   └── web_scraper.py
├── custom_tools/        # 可扩展自定义工具
├── memory/              # 三层记忆系统
├── server/              # Quart HTTP + SSE 服务器
│   ├── app.py           # 应用工厂
│   ├── routes.py        # API 端点
│   └── session.py       # 会话管理
├── desktop/             # 桌面前端 + 窗口管理
│   ├── window.py        # pywebview 窗口
│   ├── index.html       # 聊天界面
│   ├── css/style.css    # 样式
│   └── js/              # 前端逻辑（app/stream/components）
├── ui/                  # 对话持久化
│   └── conversations.py
└── utils/
```

## 🛠️ 开发

```bash
# 浏览器开发模式（热重载需手动刷新）
poetry run assistant-bird --dev

# 测试
poetry run pytest                 # 全部
poetry run pytest -k "memory"     # 按关键字

# 代码质量
poetry run ruff check src/ tests/  # Lint
poetry run mypy src/               # 类型检查
```

### 平台注意事项

| 平台 | Python | GUI 依赖 |
|------|--------|---------|
| Linux | 系统 Python 3.12（需 `python3-gi` + `gir1.2-webkit2-4.1`） | GTK WebKit |
| Windows | 任意 Python 3.12+ | 系统内置 Edge WebView2 |
| macOS | 任意 Python 3.12+ | 系统内置 WKWebView |

> Linux 用户注意：miniconda/anaconda 自带的 Python 通常没有 `gi`（PyGObject）支持，建议使用系统 Python 并通过 `poetry env use /usr/bin/python3.12` 切换。

## 🤝 贡献

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- 🐛 Bug 报告 → [Issues](https://github.com/lkk031/bird-assistant/issues)
- 💡 功能建议 → [Discussions](https://github.com/lkk031/bird-assistant/discussions)
- 📖 开发记录 → [CHANGELOG.md](CHANGELOG.md)
- 🤖 Claude Code 指南 → [CLAUDE.md](CLAUDE.md)

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)。
