# 开发记录 (Changelog)

## Phase 1: 基础框架 — 单 Agent 对话 (2026-06-04)

### 🎯 目标
从零搭建可对话的 Web 聊天界面，DeepSeek 驱动，流式输出。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `pyproject.toml` | Poetry 项目配置，定义全部依赖 |
| `.gitignore` | Python 标准忽略 + data/ / workspace/ |
| `.env.example` | 环境变量模板（DeepSeek / Mem0 / 路径配置） |
| `README.md` | 项目说明 + 快速开始 |
| `LICENSE` | MIT 开源协议 |
| `chainlit.md` | Chainlit 欢迎页（能力展示 + 隐私说明） |
| `src/assistant_bird/__init__.py` | 包初始化 |
| `src/assistant_bird/main.py` | Chainlit 入口（启动 + import callbacks） |
| `src/assistant_bird/config.py` | pydantic-settings 配置加载（单例 + 自动创建数据目录） |
| `src/assistant_bird/logging_config.py` | structlog 结构化日志（开发模式彩色 / 生产 JSON） |
| `src/assistant_bird/llm/deepseek.py` | ChatDeepSeek 工厂（流式 / 重试 / 配置化） |
| `src/assistant_bird/graph/state.py` | AssistantState TypedDict（messages + 5辅助字段） |
| `src/assistant_bird/graph/builder.py` | 单节点 chat graph（START → chat → END） |
| `src/assistant_bird/graph/checkpointer.py` | SQLite 检查点封装（暂未使用） |
| `src/assistant_bird/ui/callbacks.py` | Chainlit 生命周期（on_chat_start / on_message / on_chat_end） |
| `src/assistant_bird/ui/starters.py` | 4 个对话快捷入口 |
| `src/assistant_bird/ui/renderers.py` | 自定义渲染（Agent 切换 / 工具调用） |
| `src/assistant_bird/agents/__init__.py` | 占位 |
| `src/assistant_bird/tools/__init__.py` | 占位 |
| `src/assistant_bird/memory/__init__.py` | 占位 |

### 🔧 技术选型
- **LLM**: langchain-deepseek (deepseek-chat)
- **UI**: Chainlit 2.x
- **Graph**: LangGraph StateGraph (单节点)
- **配置**: pydantic-settings
- **日志**: structlog
- **包管理**: Poetry
- **Lint**: ruff (line-length=100, py311)

### ✅ 验证
- 所有模块导入成功
- Chainlit 服务启动 → http://localhost:8000
- DeepSeek API 调用 → HTTP 200，流式响应正常

---

## Phase 2: 多智能体系统 — Supervisor + 5 Agents + 搜索 (2026-06-04)

### 🎯 目标
升级为 Supervisor 多 Agent 架构，4 个专业 Agent + DuckDuckGo 搜索工具。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `agents/general.py` | 通用对话 Agent（无工具，处理日常对话/写作/推理） |
| `agents/research.py` | 研究 Agent（web_search 工具，网络搜索 + 事实核查） |
| `agents/filesystem.py` | 文件操作 Agent（read_file + list_directory 工具，路径沙箱） |
| `agents/memory_agent.py` | 记忆 Agent（Phase 2 占位，Phase 3 升级为真实工具） |
| `agents/supervisor.py` | 主管 Agent（langgraph-supervisor，handoff 委派） |
| `tools/web_search.py` | DuckDuckGo 搜索工具（@tool 装饰器，DDGS） |
| `tools/registry.py` | 工具注册中心（全局单例，get_tools / register） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `graph/builder.py` | 单节点图 → Supervisor 图（4 子 Agent + InMemorySaver） |
| `graph/checkpointer.py` | SqliteSaver → InMemorySaver（langgraph-checkpoint-sqlite 未安装） |
| `ui/callbacks.py` | 新增 Agent 切换显示 + 工具调用可视化 |

### 🔧 架构变化
```
Phase 1: User → Chat Node → LLM → Response

Phase 2: User → Supervisor → 委派到 →
           ├── general_agent    (无工具)
           ├── research_agent   (web_search)
           ├── file_ops_agent   (read_file, list_directory)
           └── memory_agent     (占位)
         → 回流 Supervisor → Response
```

### ✅ 验证
- 5 个 Agent 全部成功导入
- Supervisor 图编译成功 (agent_count=4)
- InMemorySaver 正常工作
- Agent 切换在 UI 中正确显示
- web_search 成功调用 DuckDuckGo

---

## Phase 3: 三层记忆系统 — Mem0 + Chroma + SQLite (2026-06-04)

### 🎯 目标
实现跨会话的长期记忆，支持个人事实、知识文档、对话历史三层存储。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `memory/mem0_client.py` | Mem0 托管 API 封装（search / add / get_all / delete，自动提取结构化事实） |
| `memory/vector_store.py` | Chroma 嵌入式向量库（语义搜索 / 文档摄入 / 删除） |
| `memory/conversation_db.py` | SQLite 对话历史（save / get_recent / search / get_summary_for_context） |
| `memory/memory_manager.py` | 三合一编排器（get_context 并行搜索 + store_conversation 后处理） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `agents/memory_agent.py` | 占位 → 4 个真实工具（recall_memories / remember_fact / search_documents / list_facts） |
| `ui/callbacks.py` | on_message 新增：对话前 memory_context 注入 + 对话后 store_conversation |

### 🔧 记忆数据流
```
每轮对话:
1. 用户输入 → MemoryManager.get_context(query, user_id)
   ├─ Mem0:       语义搜索个人偏好/事实
   ├─ Chroma:     相似度搜索知识文档
   └─ SQLite:     加载最近5轮对话摘要
2. 上下文 → AssistantState.memory_context
3. Supervisor 带记忆上下文决策委派
4. 回复完成 → MemoryManager.store_conversation()
   ├─ SQLite:     写入 user + assistant 消息
   └─ Mem0:       API 自动提取结构化事实存储
```

### ✅ 验证
- Mem0 客户端启用 (MEM0_API_KEY 有效)
- Chroma 向量库正常 (PersistentClient, cosine 空间)
- SQLite 对话记录可读写 (WAL 模式)
- MemoryManager.get_context 正常整合三层记忆
- MemoryManager.store_conversation 正常写入

---

## 版本历史

| 版本 | Git Tag | 日期 | Phase | 内容 |
|------|---------|------|-------|------|
| v0.1.0 | - | 2026-06-04 | P1 | 单 Agent 对话 + DeepSeek + Chainlit |
| v0.2.0 | - | 2026-06-04 | P2 | 多 Agent Supervisor + 搜索 |
| v0.3.0 | - | 2026-06-04 | P3 | Mem0 + Chroma + SQLite 三层记忆 |
