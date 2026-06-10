---
description: "40KB PRD 刷回 Confluence Server 整页，绕过 MCP args 阈值走 Python urllib，并修了 markdown 里 raw `<br>` 导致的 XHTML 解析 400"
---

# 大 markdown 同步到 Confluence Server——XHTML 自闭合必须显式修正

日期: 2026-05-11
角色: AI工程

## 背景

AI 销售 0 转体 PRD 改完一版，整文件 40KB（18.8k 字符 markdown → 28.8k 字符 HTML），需要刷回 Confluence Server 页面 1073050185（覆盖 v18）。

## 经过：踩了 2 个连续的坑

### 坑 1：MCP inline 调 confluence_update_page，args 必失败

PRD 是 40KB 内容，按沉淀过的原则 `2026-05-09-LLM工具调用args超阈值会丢失.md`，> 2KB 就该走脚本路径，不要试 inline 提交。

→ 直接写 Python urllib + Confluence Server REST API，绕过 LLM 输出端的长度限制。Token 从 `~/.cursor/mcp.json` 的 `mcpServers.mcp-atlassian.env.CONFLUENCE_PERSONAL_TOKEN` 取出，用 `Authorization: Bearer <token>`。

### 坑 2：Confluence storage format 是严格 XHTML，markdown 转换后必须显式自闭合

Python `markdown` 库默认输出近似 HTML5（void element 不自闭合），但 Confluence Server PUT `body.storage.value` 走的是**严格 XHTML 解析**。第一次 PUT 报 400：

```
Error parsing xhtml: Unexpected close tag </th>; expected </br>.
 at [row,col]: [365,28]
```

定位到的是 markdown table cell 里写的 raw `<br>`（用户在 markdown 里直接写的，被 passthrough 不会被 `nl2br` 扩展处理成 `<br />`），表格闭合时 XHTML 解析器认为 `<br>` 没闭合所以 `</th>` 非法。

**修复**：HTML 输出后用 3 个 regex 把 void element 统一改成自闭合：

```python
html = re.sub(r"<br\s*>", "<br/>", html)
html = re.sub(r"<hr\s*>", "<hr/>", html)
html = re.sub(r"<img([^>]*?)(?<!/)>", r"<img\1/>", html)
```

第二次 PUT 直接 OK，v18 → v19。

## 关键收获

1. **Confluence Server 的 storage format 是严格 XHTML，不是 HTML**。所有 void element（`<br>`、`<hr>`、`<img>`、`<input>`、`<meta>`、`<link>`）必须显式自闭合（`<br/>`）。这是 markdown → storage 的最常见 400 错因。

2. **Python `markdown` 库的 `nl2br` 扩展生成的换行是 `<br />` 自闭合，但 markdown 中用户写的 raw `<br>` 会原样输出**。要么禁止 markdown 里 raw HTML，要么对输出做兜底正则修正。后者更省心。

3. **markdown 库 + `tables` + `fenced_code` + `nl2br` + `sane_lists` 四个扩展**对中文 PRD 的格式还原度足够，不需要更重的 mistune 或 markdown-it-py。

4. **Confluence Server PUT 流程**：先 GET `?expand=version` 拿当前 version 号，PUT 时 `version.number` 必须严格 +1，否则 409 冲突。

5. **PUT 成功返回 200**（不是 204），response body 是更新后的 page 对象。脚本判 status in (200, 204) 兼容两种实现。

## 配套技能

已抽取脚本模板到 → `各角色目录/AI工程/技能/2026-05-11-markdown同步到Confluence-Server的Python脚本.md`

## Triggers

- "Confluence 上传 400"
- "Error parsing xhtml"
- "Unexpected close tag"
- "markdown to confluence storage"
- "br hr img 自闭合"
- "Confluence Server REST API PUT"
- "markdown 同步 Confluence"
