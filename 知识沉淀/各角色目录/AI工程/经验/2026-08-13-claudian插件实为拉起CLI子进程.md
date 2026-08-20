---
description: "Obsidian Claudian 插件不是直连 API 的聊天插件，而是拉起 Claude Code/Codex CLI 子进程，必须先在机器上装好 CLI 才能用。"
---

# Claudian 插件实为拉起 CLI 子进程

日期: 2026-08-13
角色: AI工程

## 背景

用户配 Obsidian Claudian 插件接 DeepSeek，按官方文档配置仍失败，UI 只显示 "Message was not sent. Please try again."，无网络请求、无 console 报错。

## 经过

读 Claudian 2.1.3 插件源码定位根因：Claudian 不是直连 API 的聊天插件，而是拉起 Claude Code / Codex CLI 子进程作为 agent（manifest 描述 + 代码中 cliResolver / child_process / spawn 证据）。用户机器上 `claude`、`codex` 均未安装 → `prepare()` 阶段 `supervisor.acquire()` 起进程失败 → 抛 `ChatExecutionPreHandoffError` → UI 只显示发送失败。

## 关键收获

- Claudian 依赖本机已安装的 Claude Code 或 Codex CLI 作为后端，插件本身只是 UI 壳。
- 配 DeepSeek 时 base_url 要用 Anthropic 格式（https://api.deepseek.com/anthropic），因为 Claudian 基于 Anthropic SDK。
- 排查「消息发不出去但无报错」时，先确认插件到底直连 API 还是拉起本地 CLI 子进程。

## Triggers

- Claudian / Obsidian 插件 / Message was not sent / DeepSeek anthropic base_url / 拉起 CLI 子进程
