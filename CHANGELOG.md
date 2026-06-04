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
| v0.4.0 | - | 2026-06-04 | P4 | 网页抓取 + 文件写安全 + 测试套件 |
| v0.5.0 | - | 2026-06-04 | P5 | 文档完善 + 错误处理 + 开源就绪 |

---

## Phase 4: 网页抓取 + 文件写安全 + 测试 (2026-06-04)

### 🎯 目标
添加网页抓取工具、完善文件操作安全机制、建立测试体系。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `tools/web_scraper.py` | 双工具：scrape_webpage（httpx+BeautifulSoup 网页提取）+ search_and_scrape（搜索+自动抓取） |
| `tests/__init__.py` | 测试包 |
| `tests/conftest.py` | 共享 fixtures（临时目录 + 单例清理 + 环境隔离） |
| `tests/test_tools.py` | 工具测试（WebSearch / WebScraper / FileOps / ToolRegistry）— 20 个用例 |
| `tests/test_memory.py` | 记忆测试（VectorStore / ConversationDB / Mem0Client / MemoryManager）— 13 个用例 |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `tools/registry.py` | 新增 scrape_webpage 和 search_and_scrape 注册 |
| `agents/research.py` | 工具从 1 个升级到 3 个（web_search + scrape_webpage + search_and_scrape） |
| `agents/filesystem.py` | 新增 write_file（覆盖保护）+ search_files（glob 搜索）；统一 _validate_path 沙箱 |

### 🔧 安全机制
- **路径沙箱**: `_validate_path()` 统一验证，拒绝 workspace 外的任何路径
- **覆盖保护**: write_file 检测到已存在文件时拒绝写入，提示用户确认
- **二进制检测**: read_file 捕获 UnicodeDecodeError，明确告知用户
- **抓取安全**: 10s 超时、User-Agent 声明、内容类型检测、8KB 截断

### ✅ 测试结果
```
30 passed, 0 failed in 4.41s

tests/test_tools.py   — 20 passed ✅
tests/test_memory.py  — 13 passed ✅
```

覆盖范围:
- ✅ DuckDuckGo 搜索集成测试
- ✅ 网页抓取（无效 URL / 不存在域名）
- ✅ 文件读写（读/写/覆盖/不存在/空目录/搜索/沙箱）
- ✅ 工具注册中心
- ✅ Chroma 向量存储（增删查）
- ✅ SQLite 对话（存储/检索/搜索/摘要）
- ✅ Mem0（禁用模式优雅降级）
- ✅ MemoryManager 编排

---

## Phase 5: 打磨与开源 (2026-06-04)

### 🎯 目标
完善文档、增强错误处理、为开源发布做准备。

### 📦 新增文件
| 文件 | 说明 |
|------|------|
| `CONTRIBUTING.md` | 贡献指南（开发环境 / 架构 / 如何添加 Agent / 工具 / 测试） |

### 🔄 修改文件
| 文件 | 变化 |
|------|------|
| `README.md` | 重写：badges + ASCII 架构图 + 特性表 + 项目结构 + 开发命令 |
| `chainlit.md` | 更新能力总览 + 实用示例 + 隐私说明 |
| `ui/starters.py` | 对话入口更新为当前功能（搜索 / 写作 / 记忆 / 文件） |
| `llm/deepseek.py` | 新增 `retry_call` 函数 + `is_retryable_error` + 3次重试 + 60s 超时 |

### 🔧 错误处理增强
- **DeepSeek 重试**: 指数退避（2s → 4s → 8s），识别 rate_limit/timeout/connection 等可重试错误
- **API 超时**: 60s 请求超时防止永久挂起
- **配置检查**: 启动时友好提示缺失 API Key + 获取链接

### ✅ 验证
```
30 passed, 0 failed ✅
ruff check: All checks passed ✅
chainlit server: 启动正常 ✅
```
