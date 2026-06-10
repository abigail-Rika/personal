---
description: "Confluence MCP 接入：从链接提取 pageId 直接拉取内容，工具速查表"
---

# Confluence MCP 接入：遇到公司文档链接可以直接拉取内容

日期: 2026-03-27
角色: AI工程

## 背景

用户分享了一个 Confluence 链接（keyfrom 规范优化文档），需要归档到本地知识库。以前遇到这种场景要么靠用户手动复制粘贴，要么尝试 WebFetch 但公司 Confluence 需要登录会被拦截。

## 经过

1. 发现已配置 `user-mcp-atlassian` MCP 服务器，查看工具列表后找到 `confluence_get_page`
2. 从 URL 的 `pageId=1003991941` 提取页面 ID，调用 MCP 成功拿到完整页面内容（markdown 格式）
3. 将内容整理后归档为本地 md 文件

## 关键收获

1. **Confluence 链接的 page_id 直接可用**：URL 中 `pageId=xxx` 的值就是 `confluence_get_page` 的参数，无需额外查找
2. **MCP 比 WebFetch 靠谱**：公司内网页面需要 SSO 登录，WebFetch 拿到的是登录页，MCP 已经做好了认证
3. **convert_to_markdown=true 直接出 md**：省去手动格式转换，适合直接归档

## 可用工具速查

MCP 服务器：`user-mcp-atlassian`

### 常用工具

| 工具 | 用途 | 关键参数 |
|------|------|---------|
| `confluence_get_page` | 按 ID 或标题获取页面内容 | `page_id` 或 `title` + `space_key` |
| `confluence_search` | 搜索页面 | 搜索关键词 |
| `confluence_get_comments` | 获取页面评论 | `page_id` |
| `confluence_get_page_children` | 获取子页面列表 | `page_id` |
| `confluence_get_page_images` | 获取页面中的图片 | `page_id` |
| `confluence_get_attachments` | 获取附件列表 | `page_id` |

### 典型场景

- **用户丢来一个 Confluence 链接** → 提取 pageId → `confluence_get_page` → 归档/分析
- **需要查某个主题的文档** → `confluence_search` → 找到后 `confluence_get_page`
- **需要看某文档的讨论** → `confluence_get_comments`

## Triggers

- "confluence"
- "wiki 链接"
- "confluence.zhenguanyu.com"
- "归档文档"
- "拉取公司文档"
