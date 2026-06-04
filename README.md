# 🐦 鸟助手 (Assistant-Bird)

一个开源的智能个人 AI 助手，具备多智能体协作、长期记忆、Web 搜索等能力。

## ✨ 特性

- 💬 **智能对话** — 基于 DeepSeek 大模型，自然流畅的中文交互
- 🔍 **网络搜索** — 实时搜索互联网获取最新信息（开发中）
- 📁 **文件操作** — 本地文件读写与管理（开发中）
- 🧠 **长期记忆** — Mem0 驱动的跨会话记忆系统（开发中）
- 🤖 **多智能体协作** — LangGraph Supervisor 模式，多个专业 Agent 协同（开发中）
- 🖥️ **Web 界面** — Chainlit 驱动的现代化聊天界面
- 🔒 **本地优先** — 数据存储在本地，保护隐私

## 🚀 快速开始

### 前提条件

- Python 3.11+
- Poetry（包管理器）
- DeepSeek API Key（[获取](https://platform.deepseek.com/)）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd assistant-bird

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 安装依赖
poetry install

# 启动
poetry run assistant-bird
# 或者
chainlit run src/assistant_bird/main.py
```

浏览器打开 `http://localhost:8000` 即可使用。

## 🏗️ 架构

```
用户 → Chainlit UI → Supervisor Agent → 路由到 →
  ├── Research Agent   (Web搜索+抓取)
  ├── File Ops Agent   (文件读写)
  ├── Memory Agent     (记忆存取)
  └── General Agent    (通用对话)
```

## 📂 项目结构

```
assistant-bird/
├── src/assistant_bird/
│   ├── main.py              # 入口
│   ├── config.py            # 配置
│   ├── llm/deepseek.py      # LLM 工厂
│   ├── graph/               # LangGraph 图
│   ├── agents/              # Agent 定义
│   ├── tools/               # 工具实现
│   ├── memory/              # 记忆系统
│   └── ui/                  # Chainlit UI
├── data/                    # 运行时数据
└── tests/                   # 测试
```

## 📄 许可证

MIT License
