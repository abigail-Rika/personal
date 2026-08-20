# agent-chats 备份说明

这里存放的是 **Cursor 聊天记录的文本导出**，按日期分文件夹。

## 这个备份能做什么

- 按关键词搜索历史对话（用 Grep 或全局搜索）
- 回顾之前的讨论过程、方案设计、决策记录
- 从旧对话中找回曾经生成过的代码/prompt/配置

## 这个备份不能做什么

- **不能恢复 Cursor 界面里的聊天列表**（Cursor 聊天存在应用内部数据库，和这里无关）
- **不能让 AI "记住"历史对话**（每次新对话都是从零开始）
- **不是 Agent 配置文件**（顶部下拉里的自定义 Agent 靠 `.cursor/agents/*.md`，不是这里）

## 容易搞混的三样东西

| 东西 | 位置 | 作用 |
|------|------|------|
| 聊天记录备份 | `backups/agent-chats/` (这里) | 人工查阅历史对话 |
| Agent 配置 | `.cursor/agents/*.md` 或 `~/.cursor/agents/*.md` | 聊天顶部出现的自定义 Agent |
| Rules / Context | `.cursor/rules/*.mdc`、`CLAUDE.md` | AI 每次对话自动加载的"记忆" |

## 想让 AI 持续记住某些信息？

把信息写进 `.cursor/rules/` 下的 `.mdc` 文件或 `CLAUDE.md`——这才是跨对话的"记忆"。
