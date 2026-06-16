# Android 客户端设计方案

> 日期：2026-06-16 | 状态：待审阅

## 目标

为 assistant-bird（鸟助手）开发 Android 原生客户端，通过 WiFi 局域网连接现有 Python 后端，实现手机端聊天交互。

## 架构

```
开发机 (现有 Python 后端)          WiFi 局域网          Android 手机
┌──────────────────────┐                              ┌──────────────────────┐
│ Hypercorn :19900      │ ←───── HTTP/SSE ────→        │ Kotlin + Compose     │
│ Quart + LangGraph     │                              │ Material 3           │
│ DeepSeek API          │                              │ OkHttp SSE Client    │
│ 代码完全不变            │                              │ 全新代码              │
└──────────────────────┘                              └──────────────────────┘
```

- 开发机作为服务器，代码不变
- 后端启动时打印局域网 IP + 端口
- Android 端首次启动输入服务器地址，后续记住
- 阶段一用开发机直接跑，先跑通流程

## 技术栈

| 层级 | 选择 | 理由 |
|------|------|------|
| 语言 | Kotlin | Android 官方语言 |
| UI | Jetpack Compose | 声明式，代码量少 |
| 主题 | Material 3 | 自带暗色适配 |
| HTTP | OkHttp 4 | 最成熟稳定 |
| SSE | 手动解析 | 对标 stream.js，按行解析 |
| 状态管理 | ViewModel + StateFlow | Compose 官方搭配 |
| 持久化 | DataStore | 存服务器地址等配置 |
| Markdown | compose-markdown | 开源库 |

minSdk 26 (Android 8.0)。

## 项目结构

```
app/src/main/java/com/assistantbird/
├── MainActivity.kt
├── ui/
│   ├── theme/Theme.kt
│   ├── screen/
│   │   ├── ChatScreen.kt
│   │   └── SetupScreen.kt
│   ├── component/
│   │   ├── MessageBubble.kt
│   │   ├── ToolCard.kt
│   │   ├── ConversationList.kt
│   │   └── InputArea.kt
├── network/
│   ├── ApiClient.kt
│   └── SseClient.kt
├── model/
│   ├── Message.kt
│   ├── Conversation.kt
│   └── SseEvent.kt
├── viewmodel/
│   └── ChatViewModel.kt
└── data/
    └── SettingsStore.kt
```

## 数据流

### SSE 事件类型（与后端完全对齐）

| SSE event | 后端 payload | Android 处理 |
|-----------|-------------|-------------|
| `token` | `{"text": "..."}` | 追加到当前 AI 消息文本 |
| `agent_switch` | `{"agent": "...", "display": "..."}` | 显示 agent 标签 |
| `tool_start` | `{"name": "...", "input": {...}}` | 创建折叠工具卡片 |
| `tool_end` | `{"name": "...", "output": "..."}` | 工具卡片展开填充 |
| `thinking` | `{"text": "💭"}` | 首次收到显示思考状态 |
| `system` | `{"message": "..."}` | 插入灰色系统消息 |
| `done` | `{}` | 结束流，markdown 渲染，更新对话列表 |
| `error` | `{"type": "...", "message": "..."}` | 显示错误提示 |

### 一次对话完整流程

```
用户输入 → ViewModel.sendMessage()
  → ApiClient POST /chat {message}
  → SseClient 逐行解析 SSE
  → Flow<SseEvent> 发射事件
  → ViewModel 更新 StateFlow
  → Compose UI recomposition
  → done 事件 → markdown 渲染
```

### API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/chat` | 发送消息 (SSE) |
| GET | `/conversations` | 对话列表 |
| POST | `/conversations/new` | 新建对话 |
| POST | `/conversations/switch` | 切换对话 |
| GET | `/messages/{threadId}` | 历史消息回放 |
| DELETE | `/conversations/{threadId}` | 删除对话 |
| GET | `/export/{threadId}` | 导出 Markdown |
| GET | `/health` | 健康检查 |

## UI 设计

### 布局（单屏，手机适配）

```
┌──────────────────────────┐
│  🐦 鸟助手           ☰   │  TopAppBar
│  192.168.1.xx          │  服务器地址
├──────────────────────────┤
│                          │
│         消息列表          │  LazyColumn
│   · 用户气泡 (蓝，右)     │
│   · AI 气泡 (灰，左)      │
│     · agent 标签         │
│     · 工具卡片            │
│                          │
├──────────────────────────┤
│ 📎              [输入框] ➤│  InputArea
└──────────────────────────┘

Drawer (左滑/☰):
  ✚ 新对话
  ────────────
  对话1 · 3条消息
  对话2 · 12条消息
  ...
```

### 三种气泡

- **用户气泡**：蓝色底 `#2d7bff`，右对齐
- **AI 气泡**：灰色底 `#353652`，左对齐，包含 agent 标签和工具卡片
- **系统消息**：居中灰色小字，无气泡

### 主题色（与桌面一致）

```
背景:    #1a1b26
气泡:    #252634
用户:    #2d7bff
AI:      #353652
文字:    #e8e8ed
辅助:    #9e9eae
强调:    #2d7bff
错误:    #ff5555
```

## 开发步骤

### 第 1 步：项目骨架
- Android Studio 新建 Kotlin + Compose 项目
- 添加依赖：OkHttp, compose-markdown, DataStore
- AndroidManifest 配置网络权限、明文 HTTP 允许

### 第 2 步：数据模型 + 网络层
- `model/` 下的 data class
- `SettingsStore.kt` — 存储服务器地址
- `ApiClient.kt` — REST 调用
- `SseClient.kt` — SSE 流解析 (对标 stream.js)

### 第 3 步：Theme + SetupScreen
- Material 3 暗色主题
- 首次启动输入服务器地址，保存到 DataStore

### 第 4 步：ChatViewModel
- 核心状态管理
- sendMessage / switchConversation / newConversation

### 第 5 步：ChatScreen + UI 组件
- InputArea、MessageBubble、ToolCard
- LazyColumn 消息列表
- 流式逐字渲染

### 第 6 步：NavigationDrawer
- 对话列表、切换、删除
- 历史消息回放

### 第 7 步：桌面端小改动
- `window.py` 启动时输出局域网 IP
- 确认防火墙放行 19900

### 第 8 步：联调测试
- 端到端验证：消息、流式、历史、切换、错误处理

## 不纳入本次范围

- 文件上传（/upload 端点）
- 推送通知
- 语音输入
- App 商店分发
- 对话导出到手机存储（暂用浏览器下载）
- 离线模式

## 后端改动

仅一处：`window.py` 启动时自动打印局域网 IP，方便手机填写。

## 风险点

1. **明文 HTTP**：Android 9+ 默认禁止 HTTP，需显式配置 `usesCleartextTraffic`
2. **WiFi 网络隔离**：部分路由器开启 AP 隔离，设备间无法通信
3. **SSE 解析健壮性**：确保和 `stream.js` 行为一致（半行 buffer、chunk 分割）
4. **markdown 渲染性能**：长消息使用 compose-markdown 需关注主线程负载
