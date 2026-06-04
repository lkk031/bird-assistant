# 贡献指南

感谢你对鸟助手 (Assistant-Bird) 的关注！

## 开发环境

### 前提

- Python 3.11+
- Poetry
- DeepSeek API Key

### 设置

```bash
git clone https://github.com/lkk031/bird-assistant.git
cd bird-assistant
cp .env.example .env
# 编辑 .env，填入 API Key

poetry install
poetry run chainlit run src/assistant_bird/main.py -w
```

## 项目架构

鸟助手基于 **LangGraph Supervisor 模式**：

- `graph/builder.py` — 图组装入口
- `agents/` — 每个 Agent 是独立的 `create_react_agent` 图
- `tools/` — LangChain `@tool` 函数，注册在 `registry.py`
- `memory/` — Mem0 + Chroma + SQLite 三层记忆
- `ui/callbacks.py` — Chainlit 生命周期

详见 [README.md](README.md) 的架构图。

## 如何贡献

### 添加新 Agent

1. 在 `agents/` 创建 `<name>.py`
2. 定义系统提示和工具列表
3. 实现 `create_<name>_agent(model) -> CompiledStateGraph`
4. 在 `graph/builder.py` 的 `sub_agents` 列表中注册

### 添加新工具

1. 在 `tools/` 创建 `<name>.py`
2. 使用 `@tool` 装饰器定义函数
3. 在 `registry.py` 注册
4. 分配给需要的 Agent

### 添加测试

1. 在 `tests/` 创建 `test_<name>.py`
2. 使用 `conftest.py` 中的 fixtures
3. 运行 `poetry run pytest -v`

## 代码风格

- 行宽: 100 字符
- Python 3.11+ 类型注解（`list[dict]` 而非 `List[Dict]`）
- 中文系统提示，英文代码注释
- 使用 `structlog` 日志，不 `print`

```bash
poetry run ruff check .    # Lint
poetry run ruff check --fix . # 自动修复
poetry run mypy src/       # 类型检查
```

## 提交指南

- 提交信息用中文或英文均可
- 一个提交做一件事
- 参考 [CHANGELOG.md](CHANGELOG.md) 了解历史

## 行为准则

保持友善、建设性。这是个人开源项目，欢迎所有水平的贡献者。
