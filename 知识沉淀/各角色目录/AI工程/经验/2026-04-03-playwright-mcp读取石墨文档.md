---
description: "用 Playwright MCP 读取需要登录的石墨文档：navigate + evaluate('.ql-editor').innerText"
---

# 用 Playwright MCP 读取需要登录的石墨文档

日期: 2026-04-03
角色: AI工程

## 背景

用户分享了石墨文档链接（shimo.zhenguanyu.com），需要读取文档内容来理解大促需求。WebFetch 工具直接抓取超时/失败，因为石墨文档需要登录认证。

## 经过

1. **WebFetch 失败**：直接 fetch URL 超时，返回空
2. **Playwright MCP navigate**：用 `browser_navigate` 打开 URL，第一次 snapshot 为空（页面未完全加载/需要认证），但截图显示页面实际加载成功（有登录态时）
3. **browser_evaluate 提取内容**：用 JS 表达式 `document.querySelector('.ql-editor').innerText` 一次性提取全文，得到完整的文档文本

## 关键收获

1. **石墨文档的内容在 `.ql-editor` 元素内**，用 `innerText` 可提取纯文本，保留换行和层级结构
2. **Playwright MCP 的 snapshot（accessibility tree）对石墨文档不好用**，返回空。直接用 `browser_evaluate` + `innerText` 更可靠
3. **前提是浏览器有登录态**。Playwright MCP 使用的 Chrome 用户数据目录在 `~/Library/Caches/ms-playwright/mcp-chrome-*`。如果没有登录态，页面会重定向到登录页。已有 Chrome 会话运行时会冲突（"正在现有的浏览器会话中打开"），需要关闭其他 Chrome 窗口
4. **如果浏览器冲突**，先尝试用其他方式（让用户贴内容/截图），不要死磕

## 可复用的代码片段

```javascript
// Playwright MCP 提取石墨文档内容
// Step 1: navigate
browser_navigate({ url: "https://shimo.zhenguanyu.com/docs/xxxxx/" })

// Step 2: evaluate 提取文本
browser_evaluate({
  function: "() => { const editor = document.querySelector('.ql-editor'); if (editor) return editor.innerText; return document.body.innerText; }"
})
```

## Triggers
- "石墨文档"
- "shimo"
- "读取需要登录的页面"
- "Playwright MCP 提取内容"
