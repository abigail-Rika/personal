---
description: "把本地 markdown 文件同步到 Confluence Server 已有页面（覆盖更新）的可复用 Python 脚本模板。绕过 MCP inline args 长度限制，处理 XHTML 自闭合，处理 version +1。适用于 PRD 改完一版后整页刷回 Confluence。"
triggers:
  - "PRD 刷到 Confluence"
  - "markdown 上传 Confluence"
  - "Confluence Server 整页更新"
  - "刷 Confluence"
  - "Confluence storage format XHTML"
source:
  - "各角色目录/AI工程/经验/2026-05-11-confluence-markdown同步XHTML自闭合.md"
  - "各角色目录/AI工程/经验/2026-03-27-confluence-mcp接入实践.md"
  - "各角色目录/AI工程/原则/2026-05-09-LLM工具调用args超阈值会丢失.md"
---

# Markdown 同步到 Confluence Server 的 Python 脚本

## 何时用

- 整篇 markdown 内容 > 2KB（MCP inline args 会丢失）
- 想覆盖更新已有的 Confluence 页面（不创建新页）
- 在 Cursor 环境里，能从 `~/.cursor/mcp.json` 取到 `CONFLUENCE_PERSONAL_TOKEN`

## 3 步法

### 第 1 步：脚本（拷贝即用）

写到 `/tmp/upload_confluence.py`：

```python
#!/usr/bin/env python3
"""Confluence Server PUT update by pageId, markdown -> HTML storage format."""
import os, sys, json, re, urllib.request, urllib.error
import markdown

PAGE_ID = "1073050185"           # ← 改成目标 pageId
TITLE = "AI 销售 0 转体验课"      # ← 改成目标页标题（必须和现页一致或新标题）
BASE = "https://confluence.zhenguanyu.com"
TOKEN = os.environ["CONFLUENCE_PAT"]
MD_PATH = sys.argv[1]


def req(method, url, body=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


# 1. 取当前 version
status, page = req("GET", f"{BASE}/rest/api/content/{PAGE_ID}?expand=version")
if status != 200:
    print(f"GET failed: {status}\n{page}"); sys.exit(1)
current_ver = page["version"]["number"]
print(f"current version: {current_ver}")

# 2. md -> html + XHTML 自闭合（关键！）
md_text = open(MD_PATH).read()
html = markdown.markdown(md_text,
    extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
html = re.sub(r"<br\s*>", "<br/>", html)
html = re.sub(r"<hr\s*>", "<hr/>", html)
html = re.sub(r"<img([^>]*?)(?<!/)>", r"<img\1/>", html)
print(f"md {len(md_text)} chars -> html {len(html)} chars (xhtml-normalized)")

# 3. PUT，version 必须 +1
body = {
    "version": {"number": current_ver + 1},
    "title": TITLE,
    "type": "page",
    "body": {"storage": {"value": html, "representation": "storage"}}
}
status, resp = req("PUT", f"{BASE}/rest/api/content/{PAGE_ID}", body)
if status in (200, 204):
    print(f"PUT OK -> version {current_ver + 1}")
    print(f"URL: {BASE}/pages/viewpage.action?pageId={PAGE_ID}")
else:
    print(f"PUT failed: {status}\n{resp if isinstance(resp,str) else json.dumps(resp,ensure_ascii=False)[:2000]}")
    sys.exit(1)
```

### 第 2 步：从 mcp.json 取 token 注入环境变量

```bash
CONFLUENCE_PAT=$(python3 -c "import json;print(json.load(open('/Users/jiwenyue/.cursor/mcp.json'))['mcpServers']['mcp-atlassian']['env']['CONFLUENCE_PERSONAL_TOKEN'])") \
python3 /tmp/upload_confluence.py "path/to/your.md"
```

### 第 3 步：检查结果

成功输出：

```
current version: 18
md 18869 chars -> html 28860 chars (xhtml-normalized)
PUT OK -> version 19
URL: https://confluence.zhenguanyu.com/pages/viewpage.action?pageId=...
```

## 前置 checklist

- [ ] `python3 -c "import markdown"` 能 import（系统 Python 一般自带，没有就 `pip3 install markdown`）
- [ ] `~/.cursor/mcp.json` 里有 `mcpServers.mcp-atlassian.env.CONFLUENCE_PERSONAL_TOKEN`
- [ ] 知道目标 `pageId`（从 URL `?pageId=xxx` 取）
- [ ] 标题和目标页一致（不一致会改标题，可能违反期望）

## 常见错误 & 修法

| 现象 | 原因 | 修法 |
|---|---|---|
| `GET failed: 404 No content found with id` | pageId 不对 / token 没生效 | 检查 PAGE_ID 和 CONFLUENCE_PAT 环境变量 |
| `GET failed: 401 / authorized:false` | token 过期或权限不够 | 重新生成 PAT |
| `PUT failed: 400 Error parsing xhtml: Unexpected close tag </X>; expected </br>` | markdown 里有 raw `<br>` 等 void element 没自闭合 | 已在脚本里用 regex 处理；如果还出现，扩展 regex 覆盖其他 void element |
| `PUT failed: 409 Conflict` | version.number 没 +1，或并发被别人改了 | 重 GET 一次拿最新 version 再 PUT |
| 中文乱码 | header 没 utf-8 | 脚本里已用 `json.dumps(...).encode("utf-8")` 处理 |
| 表格被吃了 | 没启用 `tables` 扩展 | 已在脚本默认开启 |
| 代码块没渲染 | 没启用 `fenced_code` 扩展 | 已在脚本默认开启 |

## 不适用的场景

- **Confluence Cloud（atlassian.net）**：API 路径不同（`/wiki/api/v2/pages/...`），且 PUT 体格式不一样。本脚本只对 Server / Data Center 版有效。
- **创建新页**：本脚本只覆盖已有页。新建用 `confluence_create_page` MCP 工具（小内容时）或独立写 POST 脚本。
- **跨空间移动 / 父页变更**：单纯 PUT 不能改 ancestors，需要 `position` 字段或单独的 `move` API。

## 什么时候需要回溯经验

- markdown → confluence 同步失败、报 xhtml 错误
- 怀疑 MCP args 丢失导致内容截断
- 第一次给一个新页 PRD 上传，想看看完整流程是什么

原始踩坑：`各角色目录/AI工程/经验/2026-05-11-confluence-markdown同步XHTML自闭合.md`
