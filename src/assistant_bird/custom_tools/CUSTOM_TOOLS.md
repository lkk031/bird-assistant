# 自定义工具开发指南

你只需要读这个文件就能给鸟助手添加新功能。`github_trending.py` 是完整可参考的范例。

⚠️ **每次修改（新建/编辑/删除工具）都必须在 `CHANGELOG.md` 顶部追加记录，否则视为任务未完成。**

---

## 一、5 分钟速成

### 最小模板

在 `custom_tools/` 下新建 `my_tool.py`：

```python
"""一句话描述你的工具。"""

import httpx
from langchain_core.tools import tool
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

@tool
def my_tool(param1: str, param2: int = 5) -> str:
    """工具描述 —— Agent 靠这段文字决定何时调用你。

    Args:
        param1: 参数1的含义。
        param2: 参数2的含义（默认5，最大20）。

    Returns:
        格式化后的文本结果。
    """
    logger.info("my_tool: called", param1=param1)

    try:
        # 你的核心逻辑
        result = f"处理完成: {param1} x {param2}"
        return result
    except Exception as e:
        logger.error("my_tool: failed", error=str(e))
        return f"操作失败: {str(e)}"
```

### 三步接入

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1. 注册 | `tools/registry.py` | 顶部 `import`，`_tools` 字典里加一行 |
| 2. 分配 | `agents/<agent>.py` | 工具列表里加上名字，提示词里加说明 |
| 3. 测试 | 浏览器 | 对鸟助手说出触发词 |

### 具体改法示例

**`tools/registry.py`：**
```python
from assistant_bird.custom_tools.my_tool import my_tool  # 加在现有 import 下面

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {
            # ... 现有的 ...
            "my_tool": my_tool,  # 新增
        }
```

**`agents/research.py`**（如果是研究类工具）：
```python
RESEARCH_SYSTEM_PROMPT = """...
- **my_tool**: 你的工具简要说明"""  # 加到提示词里

def create_research_agent(model):
    tools = registry.get_tools([
        "web_search", ..., "my_tool",  # 加到列表里
    ])
```

---

## 二、工具编写规范

### 2.1 函数签名

```python
@tool
def tool_name(required_param: str, optional_param: int = 10) -> str:
```

- ✅ 用 `@tool` 装饰器（LangChain），不是普通函数
- ✅ 参数类型标注清楚（`str`, `int`, `bool`）
- ✅ 提供合理的默认值
- ✅ 返回 `str` —— Agent 看到的是文本
- ✅ 参数上限保护（`num = min(num, MAX)` 或 `num = max(min(num, 1), 25)`）
- ❌ 不要返回 dict/list —— Agent 看不懂结构化数据

### 2.2 Docstring —— 等于工具说明书

Agent 通过 docstring 理解工具的用途和调用时机。必须写清楚：

```python
"""用中文简短描述工具做什么。

长一些的说明：什么情况下应该用这个工具，能解决什么问题。

Args:
    param1: 参数说明，值的范围、默认值。
    param2: 参数说明。

Returns:
    返回值格式的简要描述。
"""
```

### 2.3 日志规范

```python
from assistant_bird.logging_config import get_logger
logger = get_logger(__name__)

# 关键节点记录
logger.info("tool_name: starting", param=value)       # 调用开始
logger.info("tool_name: success", result_count=n)      # 成功
logger.warning("tool_name: degraded", reason="...")    # 降级
logger.error("tool_name: failed", error=str(e))        # 失败
```

- 日志消息格式：`"模块名: 事件"`
- 用 `param=value` 格式传元数据（structlog 会结构化存储）
- 不要 `print()`，不要 `logger.info(f"...")` 写 f-string

### 2.4 错误处理

```python
@tool
def robust_tool(param: str) -> str:
    try:
        # 主逻辑
        result = do_something(param)
        return f"✅ {result}"
    except ValueError as e:
        # 预期内的错误 → 用户能看懂的消息
        return f"参数错误: {str(e)}"
    except httpx.TimeoutException:
        # 外部服务错误 → 友好提示
        return "请求超时，请稍后重试。"
    except Exception as e:
        # 未预期的错误 → 记录 + 用户消息
        logger.error("robust_tool: failed", error=str(e))
        return f"操作失败: {str(e)}"
```

**规则：工具永远不抛异常**。所有异常都 catch，返回错误字符串。Agent 会把返回值当作文本继续处理。

### 2.5 参数上限保护

```python
@tool
def my_search(query: str, num_results: int = 5) -> str:
    # 防止 Agent 传极端值
    num_results = min(num_results, 20)
    num_results = max(num_results, 1)
    ...
```

### 2.6 输出格式

返回 Markdown 格式的文本，让用户看着舒服：

```python
# 列表型结果
lines = [f"## 搜索结果: {query}\n"]
for i, item in enumerate(results, 1):
    lines.append(f"{i}. **{item.title}**")
    lines.append(f"   {item.description}")
lines.append(f"\n📊 共 {len(results)} 条结果")
return "\n".join(lines)

# 单条结果
return f"## {title}\n\n{content}\n\n🔗 来源: {url}"
```

---

## 三、常见工具模式

### 模式 A：外部 API 调用

```python
import httpx

TIMEOUT = 15.0
USER_AGENT = "AssistantBird/0.1"

@tool
def call_api(endpoint: str) -> str:
    """调用某个外部 API 获取数据。"""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(endpoint, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            data = resp.json()
        # 格式化 data → 文本
        return format_response(data)
    except httpx.HTTPStatusError as e:
        return f"API 返回错误: HTTP {e.response.status_code}"
```

### 模式 B：网页抓取

```python
import re
from bs4 import BeautifulSoup

@tool
def scrape_something(url: str) -> str:
    """抓取并解析网页。"""
    if not url.startswith(("http://", "https://")):
        return f"错误: 无效 URL '{url}'"

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
    except httpx.TimeoutException:
        return "请求超时。"

    soup = BeautifulSoup(resp.text, "html.parser")
    # 清理 → 提取 → 格式化
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:5000]  # 截断
```

### 模式 C：本地操作

参考 `agents/filesystem.py`，通过 `get_settings().workspace_root` 获取工作目录，所有路径受限在该目录下。

### 模式 D：调用其他工具

```python
@tool
def composite_tool(query: str) -> str:
    # 可以在工具内部调用其他工具
    from assistant_bird.tools.web_search import web_search
    search_result = web_search.invoke({"query": query, "num_results": 3})
    ...
```

---

## 四、Agent 分配决策

| Agent | 文件 | 适合的工具类型 |
|-------|------|---------------|
| **Research** | `agents/research.py` | 网络搜索、API 查询、数据抓取、信息聚合 |
| **File Ops** | `agents/filesystem.py` | 文件读写、目录浏览、代码生成到文件 |
| **Memory** | `agents/memory_agent.py` | 记忆存取、知识库管理 |
| **General** | `agents/general.py` | 无工具，纯对话/推理 |

**选哪个 Agent？**
- 需要联网获取信息 → Research
- 需要读写本地文件 → File Ops
- 需要存取记忆 → Memory
- 都不需要（纯聊） → General

### 创建新 Agent（如果现有 Agent 都不合适）

```python
# agents/my_new_agent.py
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = """你是 XXX 专家。你的职责是..."""

def create_my_agent(model) -> CompiledStateGraph:
    return create_react_agent(
        model=model,
        tools=[tool1, tool2],
        prompt=SYSTEM_PROMPT,
        name="my_agent",
    )
```

然后在 `graph/builder.py` 的 `sub_agents` 列表里加上 `create_my_agent(model)`。

---

## 五、测试你的工具

### 手动测试（最快）

```bash
poetry run python -c "
from assistant_bird.custom_tools.github_trending import github_trending
print(github_trending.invoke({'language': 'python', 'since': 'daily', 'max_results': 3}))
"
```

### 写单元测试

在 `tests/` 下新建 `test_my_tool.py`：

```python
class TestMyTool:
    def test_import(self):
        from assistant_bird.custom_tools.my_tool import my_tool
        assert my_tool is not None

    def test_basic_call(self):
        from assistant_bird.custom_tools.my_tool import my_tool
        result = my_tool.invoke({"param1": "test"})
        assert isinstance(result, str)
        assert len(result) > 0
```

运行：`poetry run pytest tests/test_my_tool.py -v`

### 注意事项

- 测试通过 `invoke({"param": value})` 调用，不是 `my_tool(param=value)`
- `conftest.py` 会自动设置测试环境（假的 API key + 临时目录 + 单例清理）
- 如果工具依赖网络，测试应该只测参数校验，不要真发请求

---

## 六、调试与排查

### 工具没有被调用

1. 检查 `registry.py` 是不是注册了
2. 检查 Agent 的 `get_tools([...])` 列表里有没有名字
3. 检查 Agent 的 system prompt 里是否提到了这个工具
4. 看日志：启动时会打印 `agent_count=N`

### 工具返回了但 Agent 没用到结果

- Agent 不会自动"理解"你的返回格式 —— docstring 写清楚返回值格式
- 如果是表格/列表，用 Markdown 格式化，Agent 更容易解析

### 服务重启后工具没加载

Chainlit 用 `-w` 热重载会自动重启，但如果改了 import 结构可能触发不了。手动 `Ctrl+C` 重新 `chainlit run` 最稳妥。

---

## 七、参考文件

| 文件 | 学什么 |
|------|--------|
| `github_trending.py` | 完整范例：抓取 + 解析 + 格式化 |
| `tools/web_search.py` | 最简工具：API 调用 + Markdown 输出 |
| `tools/web_scraper.py` | HTTP 客户端 + BeautifulSoup |
| `agents/filesystem.py` | 带安全校验的本地操作 + 多工具 Agent |
| `agents/research.py` | 多工具 Agent 的标准写法 |

---

## 八、速查清单

添加新工具时逐项核对：

- [ ] 文件名 `<tool_name>.py`，放在 `custom_tools/` 下
- [ ] 用 `@tool` 装饰器
- [ ] 参数有类型标注 + 默认值
- [ ] docstring 写清楚了用途和参数含义
- [ ] 所有异常都 catch，返回错误字符串
- [ ] 参数有上限保护（`min/max`）
- [ ] 返回格式化的 Markdown 文本
- [ ] 使用 `get_logger(__name__)` 记录关键日志
- [ ] 在 `tools/registry.py` 注册
- [ ] 分配给合适的 Agent（修改 `agents/*.py`）
- [ ] 手动 `invoke` 测试通过
- [ ] `ruff check` 无报错
- [ ] `pytest` 全部通过
