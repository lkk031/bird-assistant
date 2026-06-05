# 新闻搜索成功率提升方案

## 背景

当前 `custom_tools/world_news.py` 使用 8 个英文 RSS 源并行抓取。主要瓶颈：
- Google News、BBC、NPR、NYT 等在国内网络不可达
- 8 个源全失败 → 用户看到报错
- 实际上哪怕只成功 1 个源，返回 3-5 条新闻也比报错强

## 目标

将"至少一条新闻返回"的成功率从 ~30-40% 提升到 90%+。

## 实施步骤

### Step 1: 增加国内可用的新闻源（`custom_tools/world_news.py`）

在 `NEWS_SOURCES` 和 `REGION_SOURCES` 中增加以下源：

```python
# 新增到 NEWS_SOURCES（全球源）
{
    "name": "RSS Hub 环球",
    "url": "https://rsshub.app/world",
    "lang": "zh",
    "source_type": "direct",
},
{
    "name": "CGTN World",
    "url": "https://www.cgtn.com/subscribe/rss/section/world.xml",
    "lang": "en",
    "source_type": "direct",
},

# 新增到 REGION_SOURCES["china"]
{
    "name": "RSS Hub 微博热搜",
    "url": "https://rsshub.app/weibo/search/hot",
    "lang": "zh",
    "source_type": "direct",
},
{
    "name": "RSS Hub 知乎热榜",
    "url": "https://rsshub.app/zhihu/hotlist",
    "lang": "zh",
    "source_type": "direct",
},
{
    "name": "RSS Hub 百度热搜",
    "url": "https://rsshub.app/baidu/top",
    "lang": "zh",
    "source_type": "direct",
},
{
    "name": "SCMP",
    "url": "https://www.scmp.com/rss/91/feed",
    "lang": "en",
    "source_type": "direct",
},

# 新增到 REGION_SOURCES["tech"]（科技板块）
{
    "name": "RSS Hub 36氪",
    "url": "https://rsshub.app/36kr/motif/0",
    "lang": "zh",
    "source_type": "direct",
},
```

**注意**：RSS Hub（rsshub.app）是国内可访问的开源 RSS 聚合器。如果用户有自己的 RSS Hub 实例，替换 URL 前缀即可。

### Step 2: 新闻搜索模式增加 web_search 回退（`custom_tools/world_news.py`）

当前 topic 搜索只用 Google News RSS。在 `world_news` 函数的 topic 搜索分支中增加回退：

```python
# 在 topic 搜索的 except 分支中（约 line 431），改为：

except Exception as e:
    logger.warning("world_news: topic search failed, falling back to web_search",
                   topic=topic, error=str(e)[:80])
    # Fallback: use web_search for news
    from assistant_bird.tools.web_search import web_search
    try:
        result = web_search.invoke({
            "query": f"{topic} news today",
            "num_results": min(max_results, 10),
        })
        return f"## 📰 新闻搜索: {topic.strip()}\n\n"
               f"> ⚠️ Google News RSS 不可用，使用网页搜索作为备选。\n\n"
               f"{result}"
    except Exception as e2:
        logger.error("world_news: both RSS and web_search failed",
                     topic=topic, error=str(e2)[:80])
        return fail_all_msg  # 复用现有的反幻觉消息
```

### Step 3: 头条模式增加 web_search 兜底（`custom_tools/world_news.py`）

在 `_fetch_headlines` 全部失败后（约 line 365），增加一级兜底：

```python
# 在 if not items: 分支中（约 line 365），改为：

if not items:
    if failed_sources:
        # 最后手段：用 web_search 搜当日新闻
        logger.warning("world_news: all RSS sources failed, trying web_search fallback")
        from assistant_bird.tools.web_search import web_search
        try:
            result = web_search.invoke({
                "query": f"{region_label} news headlines {datetime.now(UTC).strftime('%Y-%m-%d')}",
                "num_results": min(max_results, 10),
            })
            return (
                f"## 🌍 {region_label}新闻\n\n"
                f"> ⚠️ 所有 RSS 新闻源不可用，以下为网页搜索结果（可能包含非新闻内容）。\n\n"
                f"{result}"
            )
        except Exception:
            pass  # 回退也失败，继续到反幻觉消息

    return fail_all_msg
```

### Step 4: 验证

1. 启动服务器 `poetry run chainlit run src/assistant_bird/main.py`
2. 依次测试：
   - "今天有什么新闻"（头条模式）
   - "搜索 AI 相关新闻"（topic 搜索模式）
   - "今天中国有什么新闻"（region 模式）
3. 观察日志中 `world_news: source OK` 和 `world_news: source failed` 的比例
4. 确认至少有一种模式能返回结果（不再出现"全部源失败"）

## 预期效果

- 源数量：8 → 14+（增加 6+ 个国内可用源）
- 搜索回退：RSS 失败 → 自动切 web_search
- 兜底：web_search 再失败 → 反幻觉消息（不编造）

## 不涉及的文件

- `custom_tools/read_article.py` — 不需要改动
- `agents/research.py` — 不需要改动（工具签名不变）
- `tools/registry.py` — 不需要改动
- `CHANGELOG.md` — 完成后记得追加记录
