# 自定义工具修改记录

本文件记录 `custom_tools/` 目录下所有工具的创建、修改和优化历史。

⚠️ **强制规则：对 custom_tools/ 的任何修改（新建、编辑、删除工具）都必须在本文件顶部追加记录，违者视为未完成。**

---

## 2026-06-06 — v0.5.0 新增视频搜索工具

### ✨ 新增 github_search

- 使用 GitHub REST API (`api.github.com/search`) 封装的 `@tool`
- 支持 3 种搜索：repositories（仓库）、issues（Issue+PR）、code（代码，需 Token）
- 返回 Markdown 格式化结果：仓库显示 ⭐🍴📝，Issue/PR 显示状态🟢🟣和评论数
- 支持 GitHub 高级搜索语法（language:python stars:>100 org:xxx）
- 无额外依赖，直接使用 httpx（已有）
- 友好处理速率限制（403）和认证缺失（401）

### ✨ 新增 rss_feed

- 基于 feedparser 封装的 `@tool`，解析任意 RSS 2.0 / Atom 1.0 订阅源
- HTTP 层用 httpx（已有的项目依赖），双重 SSL 回退策略（标准 SSL → verify=False）
- 输出 Markdown 格式文章列表：标题、日期、摘要（去 HTML）、链接
- 参数上限保护：limit 限制 1-20
- 新增依赖：`feedparser`（poetry add）
- URL 合法性校验（必须以 http:// 或 https:// 开头）
- 完整的异常处理：超时、HTTP 错误、DNS 错误、解析失败

### ✨ 新增 video_search

- 基于 yt-dlp 封装的 `@tool`，支持搜索 YouTube 和 B站(Bilibili) 视频
- YouTube 搜索速度快（~2s），返回完整元数据（标题、时长、播放量、作者、简介、链接）
- B站搜索需完整提取（~7s），返回标题和视频链接
- 支持三种模式：`auto`（同时搜两个平台）、`youtube`、`bilibili`
- 参数上限保护：`max_results` 限制 1-5
- 浏览器 UA 伪装绕过 B站反爬机制
- 所有异常 catch，返回中文错误提示
- 新增依赖：`yt-dlp`（poetry add）

## 2026-06-05 — v0.4.1 新闻模块可靠性修复

### 🔧 修复 `world_news.py` — 超时控制 + 反幻觉 + 降级

**问题**（来自 `news_module_issues_report.md`）：
1. 工具调用耗时 5+ 分钟（TCP connect 无响应时单一超时无效）
2. Agent 在工具失败后凭训练数据编造假新闻（幻觉）
3. 成功率极低（Google News RSS 几乎总被限流）

**修复内容**：
- **超时机制**：`httpx.Timeout(connect=5, read=10, write=5, pool=5)` 替代单一 `15.0s`，TCP connect 5s 必断
- **总超时保护**：`_fetch_headlines` 新增 `as_completed(timeout=18s)` + `TimeoutError` 取消未完成 future
- **失败追踪**：返回签名改为 `(items, sources, failed_sources)`，区分"源失败"与"源为空"
- **线程数上限**：`max_workers=min(len(sources), 5)` 防止连接风暴
- **部分降级**：部分源成功时显示结果 + 失败源列表，不完全丢弃
- **反幻觉消息**：全部失败时返回 `⚠️...请勿编造或凭记忆生成新闻内容` 显式警告
- **`_fetch_one_feed` 不再吞异常**：改为抛出，让调用者区分失败类型

### 🔧 修复 `read_article.py` — 超时 + 结构化错误

- `httpx.Timeout(connect=5, read=10, write=5, pool=5)` 替代单一超时
- 区分 `TimeoutException` / `HTTPStatusError` / `ET.ParseError` 错误类型
- 所有错误消息统一包含"请勿凭记忆编造"警告
- 未找到文章时给出具体替代方案（缩短关键词 / web_search）

### 🧠 更新 `agents/research.py` — 反幻觉提示词

- 新增 **⚠️ 关键规则** 章节：
  1. 绝对禁止编造新闻 — 工具返回 ⚠️ 错误时必须原样转达
  2. 诚实优先 — 宁可说 3 次"无法获取"也绝不编造 1 条假新闻
  3. 区分时效性 — 实时新闻依赖工具、通用知识用训练数据

### ⏱️ 效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| world_news 超时 | 5+ 分钟 | **~10s** |
| read_news_article 超时 | 5+ 分钟 | **~10s** |
| 幻觉风险 | 高 | 低（双重防护） |

### 📡 国内可用源 + web_search 回退（v0.4.1 补充）

**依据**：`news-reliability-plan.md` 三步方案

**Step 1 — 新增国内可用新闻源（8 → 14+）**：
- `NEWS_SOURCES` 新增：RSS Hub 环球、CGTN World
- `REGION_SOURCES["china"]` 新增：RSS Hub 微博热搜/知乎热榜/百度热搜、SCMP
- `REGION_SOURCES["tech"]` 新增：RSS Hub 36氪
- `TOPIC_FEEDS` 区域同时合并 `REGION_SOURCES`（如 tech 板块 + 36氪）

**Step 2 — topic 搜索增加 web_search 回退**：
- Google News RSS 失败/空 → 自动调用 `web_search` 搜 `"{topic} news today"`
- web_search 再失败 → 反幻觉消息

**Step 3 — 头条模式增加 web_search 兜底**：
- 所有 RSS 源全部失败 → `web_search` 搜当日新闻作为最后手段
- 成功时标注来源切换，失败时走反幻觉消息

**效果**：
| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 源数量 | 8 | 14+ |
| 成功率 | ~30-40% | **64%+**（7/11 源可用） |
| 降级路径 | 0（直接报错） | 2 级（RSS → web_search → 反幻觉） |

---

## 2026-06-04 — v0.4.0 天气查询

### ✅ 新建 `weather.py` — 全球天气查询

**功能**：通过城市名称查询实时天气和未来多日预报。

**技术实现**：
- 两步 API 调用：Open-Meteo Geocoding（城市名 → 坐标）→ Open-Meteo Forecast（天气数据）
- 免费无需 API Key，全球覆盖
- WMO 天气代码 → 中文描述 + emoji（46 种天气类型）
- 风向角度 → 中文方位（北/东北/东/东南/南/西南/西/西北）

**参数**：
- `city`：城市名，支持中文（北京）或英文（Tokyo）
- `forecast_days`：预报天数（1-7，默认 1）

**输出**：Markdown 表格，包含当前温度/体感温度/湿度/天气/风速风向 + 多日预报表

**注册**：`tools/registry.py` → Research Agent

---

## 2026-06-04 — v0.3.1 文章详情 + 可点击链接

### ✅ 新建 `read_news_article.py` — 文章详情查找

**功能**：根据文章标题搜索 Google News RSS，返回可点击链接和详情。
输出最多 3 个匹配结果（不同来源对同一事件的报道），每个包含：
- 文章标题 + 来源 + 发布时间
- 可点击的 Google News 链接（在浏览器中打开阅读）
- 文章摘要（如果有）

**使用场景**：用户在 `world_news` 中看到头条列表后，说「第3条详情」「这篇文章讲什么」

### 🔄 更新 `world_news.py` — 恢复可点击链接

- 头条列表现在每一条都带链接：
  - Google News 来源 → `[🔗 阅读]`（Google News 预览页，人类可点击）
  - 直接来源（BBC/Guardian 等）→ `[🔗 原文]`（**真实文章 URL**，可抓取）
- 提示语更新：引导用户使用 `read_news_article` 获取详情

### 🔄 更新 Agent 提示词
- Research Agent 新增「新闻场景专用流程」：
  1. 看新闻 → `world_news`
  2. 看某条详情 → `read_news_article(title="...")`
  3. AI 总结 → `web_search` + `scrape_webpage`

---

## 2026-06-04 — v0.3.0 多源新闻聚合

### 🔄 重构 `world_news.py` v3.0 — 多源并行聚合

**问题**：v2.0 纯 Google News RSS 单一聚合器，存在算法偏差风险。

**修复**：
- 头条模式改为**多源并行获取 + 去重 + 交错排列**
- 聚合器源：Google News（算法聚合，覆盖广）
- 直接源：BBC World、Al Jazeera、The Guardian、NPR、NYT World（编辑筛选，视角多元）
- 6 个源并发请求，总共耗时约 2 秒
- 智能去重：75% 词重叠 + 5 个以上共享词才判定为重复，不同角度的报道保留
- 交错排列：聚合器 + 直接源轮播，避免单一视角集中
- 显示所有抓取来源（即使部分内容被去重）

**当前源清单**：

| 源 | 类型 | 覆盖范围 |
|----|------|---------|
| Google News | 算法聚合 | 全球 |
| Google News 中国 | 算法聚合 | 中文 |
| BBC World | 编辑筛选 | 全球 |
| Al Jazeera | 编辑筛选 | 全球/中东 |
| The Guardian | 编辑筛选 | 全球/欧洲 |
| NPR | 编辑筛选 | 美国 |
| NYT World | 编辑筛选 | 全球 |

**话题搜索模式**：保持 Google News RSS search（唯一支持关键词搜索的免费源）

---

## 2026-06-04 — v0.2.1 摆脱 DDG 依赖

### 🔄 重构 `world_news.py` v2.0 — 纯 Google News RSS

**问题**：连续调用 DDG News API 导致 IP 级别限流（202/403 Ratelimit），影响所有 DDG 端点。
根因是 `duckduckgo-search` 旧版 v6.4.2 的冒充检测功能损坏，触发 DDG 反爬机制。

**修复**：
- 头条模式：Google News RSS（无变化）
- 话题搜索模式：从 DDG News 改为 `news.google.com/rss/search?q=<query>`
- 彻底移除 `from duckduckgo_search import DDGS` 依赖
- 移除 `time_range` 参数（Google News RSS 不支持时间过滤）

**依赖变更**：
- `duckduckgo-search` 从 6.4.2 → 7.5.5（尝试升级但 DDG News 仍限流）
- `pyproject.toml` 约束从 `^6.0.0` → `>=6.0.0`

**验证**：三种模式（国际头条 / 话题搜索 / 科技板块）全部稳定，零限流。

---

## 2026-06-04 — v0.2.0 爬虫增强 + 新闻工具重构

### 🔄 重构 `world_news.py` v1.1

**修复依据**：`workspace/爬虫错误分析报告_20260604.md`（Research Agent 发现 5 次抓取全部失败）

| 问题 | 修复 |
|------|------|
| Google RSS 返回重定向 URL → 404 | 头条模式不输出 URL，只展示标题+来源+时间 |
| DDG News 被限流 | 降级提示：建议用 web_search 替代 |

### 🔄 增强 `web_scraper.py` v2

| 特性 | 旧 → 新 |
|------|--------|
| User-Agent | 1 个固定 → 5 个浏览器 UA 轮换 |
| 请求头 | 仅 UA → 完整浏览器头（Accept-Language/Sec-Fetch/Referer） |
| 重试 | 无 → 3 次 + 指数退避（2s→5s→10s） |
| 错误分类 | 通用 → 403/404/429/5xx 各有不同提示 |
| 请求间隔 | 无 → 同域名 ≥0.5s 随机抖动 |
| HTTP | 1.1 → 2.0 |
| 超时 | 10s → 15s |

---

## 2026-06-04 — v0.1.0 初始创建

### ✅ 新建 `github_trending.py` — GitHub 热点项目追踪

**功能**：抓取 GitHub Trending 页面，发现热门开源项目。

**参数**：
- `language`：语言过滤（python/rust/go/typescript 等 40+ 语言）
- `since`：时间范围（daily/weekly/monthly）
- `max_results`：结果数量（1–25）

**技术细节**：
- 直接解析 GitHub Trending 页面的 `<article class="Box-row">` HTML 卡片
- 提取：owner/repo、描述、语言、总 star 数、fork 数、今日/本周/本月新增 star
- Markdown 格式输出

**注册**：`tools/registry.py` → `research_agent` 工具列表
```
"web_search", "scrape_webpage", "search_and_scrape", "github_trending"
```

---

### ✅ 新建 `world_news.py` v1 — 全球新闻速览

**功能**：快速了解全球大事，支持头条概览和话题搜索。

**初始实现（v1，已废弃）**：
- 头条模式：Google News RSS → 直接输出 Google 重定向 URL
- 话题模式：DuckDuckGo News 搜索

**已知问题**（见下方 v1.1 修复）：
- Google News RSS 返回的是重定向链接，无法直接抓取 → 导致 5/5 全部 404
- 无反爬虫保护 → Politico 等站点返回 403

---

## 2026-06-04 — v0.2.0 爬虫增强 + 新闻工具重构

### 🔄 重构 `world_news.py` v1.1

**修复依据**：`workspace/爬虫错误分析报告_20260604.md`（Research Agent 自动生成，发现 5 次抓取全部失败）

**核心问题**：
| 问题 | 原因 | 修复 |
|------|------|------|
| 5/5 URL 404 | Google News RSS 返回重定向链接，非真实文章 URL | 头条模式不再输出 URL，只展示标题+来源+时间 |
| Politico 403 | 默认 User-Agent 被 Cloudflare 拦截 | 用户可要求按标题搜索真实 URL 后用 web_scraper 抓取 |
| DDG 频繁 403 | 测试阶段请求太密集 | 加 3s 间隔 + 被限后等 5-8s 重试 |

**新行为**：
- 头条模式：Google News RSS → 输出标题 + 来源 + 时间（不包含 URL）
- 提示语：`💡 想阅读某条新闻的全文？告诉我标题，我用 web_search 查找真实文章链接后抓取。`
- 话题模式：DDG News → 输出真实可抓取的文章 URL
- DDG 被限流时：建议使用 web_search + scrape_webpage 两步走

**技术栈变化**：
```
v1: Google News RSS → 直接输出 URL → Agent 抓取 → 404 ❌
v1.1: Google News RSS → 只输出标题 → Agent 搜索标题 → web_search → 找到真实URL → 抓取 ✅
```

### 🔄 增强 `web_scraper.py` v2

**修复依据**：同上错误报告，建议 1-5

**新增反爬虫策略**：

| 特性 | 旧实现 | 新实现 |
|------|--------|--------|
| User-Agent | 1 个固定 UA | 5 个浏览器 UA 随机轮换 |
| 请求头 | 仅 User-Agent | 完整浏览器头（Accept/Accept-Language/Referer/Sec-Fetch-*） |
| 重试机制 | 无 | 3 次重试 + 指数退避（2s→5s→10s） |
| 403 处理 | 直接报错 | 切换 UA 重试，3 次后告知"站点拦截自动访问" |
| 404 处理 | 直接报错 | 告知"文章可能已移动，建议搜索标题" |
| 429 处理 | 无 | 增加更长的等待时间 |
| 5xx 处理 | 无 | 自动重试 |
| 请求间隔 | 无 | 同域名 ≥0.5s（随机抖动 0–0.5s） |
| HTTP 协议 | HTTP/1.1 | HTTP/2 |
| 超时 | 10s | 15s |
| HTML 清理 | script/style/nav/footer/iframe/noscript | 额外清理 `<header>` 标签 |

**User-Agent 池**：
```python
# Chrome 125 on Windows
# Safari 17.5 on macOS
# Firefox 126 on Linux
# Edge 125 on Windows
# Chrome on macOS
# → 每次请求 + 重试时随机切换
```

---

## 当前工具清单

| 工具 | 文件 | 版本 | 状态 |
|------|------|------|------|
| `github_trending` | `github_trending.py` | v1.0 | ✅ 稳定 |
| `world_news` | `world_news.py` | v1.1 | ✅ 已修复 |
| — (scraper) | `../tools/web_scraper.py` | v2.0 | ✅ 已增强 |

## 已分配的 Agent

| Agent | 工具列表 |
|-------|---------|
| **Research Agent** | `web_search`, `scrape_webpage`, `search_and_scrape`, `github_trending`, `world_news` |

---

## 已知限制

1. **DDG News 限流**：测试阶段连续调用会被限流（403 Ratelimit），生产环境对话间隔足够长，不太会触发
2. **Google News RSS URL 不可抓取**：这是 RSS 标准行为（重定向链接），已通过改变策略解决（标题搜索 → 真实 URL）
3. **GitHub Trending 仅 14 条**：非 JS 渲染下 GitHub 只返回前 14 个 repo，其余需要 JS 渲染
4. **高反爬站点**：如 Politico 使用 Cloudflare，普通 HTTP 请求即使有浏览器头也可能被拦截。报告建议 P2 阶段集成 Playwright 解决

---

*最后更新：2026-06-04 | 下次修改时请在此文件顶部追加*
