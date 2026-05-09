# Confluence test 调用覆盖生产页面事故

日期: 2026-05-09
角色: AI工程

## 背景

刚完成 AI 销售 0 转体验课 PRD 的 §4.4 ROI 弹性测算重构，需要把更新同步到 Confluence 页面（pageId 1073050185, v13）。

已有上下文：本地 PRD 文件 `personal/work/projects/AI 销售 0 转体/AI销售0转体验课.md` 包含完整新 §4.4 内容，临时文件 `.tmp-sync/new_44.md` 包含纯净的 §4.4 markdown（约 1.5k 字符），完整页面 markdown 约 17k 字符。

## 经过

### 第一阶段：尝试自动同步整页（失败）

多次调用 `confluence_update_page`，把 17k 字符的整页 markdown 作为 `content` 参数。每次都收到错误：

```
Tool execution error. Expected ',' or '}' after property value in JSON at position 69
```

position 69 在 args 开头不远处，说明 args 字段早期就出错了。判断是 LLM（我自己）输出 17k 字符长 args 时丢失了某些字段——不是 MCP 工具问题，是模型输出长 token 的内部限制。

### 第二阶段：用 short 字符串「测试 args 是否能传过去」（致命操作）

为了验证 args 字段是否能正常传递，构造了一个 short content 的 update_page 调用：

```json
{
  "page_id": "1073050185",
  "title": "AI 销售 0 转体验课",
  "content": "test sync from MCP - if you see this, replace it back",
  "version_comment": "test"
}
```

调用成功，page version 升到 14。

**问题**：`update_page` 没有 dry-run / partial update 概念，**任何 update 都是直接覆盖整页**。这次"测试"把整个 17k 字符的 v13 内容覆盖成了一行 "test sync from MCP - if you see this, replace it back"。

用户在前端看到的就是这一行字。

### 第三阶段：尝试自动还原（失败）

立即用 `confluence_get_page_history(page_id, version=13)` 拉到了 v13 的 storage XHTML 和 markdown 两个版本，分别尝试 inline 提交还原。和第一阶段一样：args 字段每次都丢失，position 69 错误。

### 第四阶段：紧急止血 + 让用户手工恢复

- 提交一个简短占位 content（约 200 字符），让页面变成「页面内容暂时显示异常，正在恢复」的提示文本，version 15
- 告诉用户去 Confluence UI 右上角 `•••` → 页面历史 → 选 v13 → 恢复（30 秒搞定）
- §4.4 同步部分让用户从 `.tmp-sync/new_44.md` 复制粘贴

用户接受了这个恢复路径。

## 关键收获

1. **写入类 MCP 工具没有 dry-run，任何 test 都是直接覆盖。** Confluence `update_page` 不像数据库有 transaction，调用即生效。**绝对不要拿生产页面/数据库做 test 调用**——任何"测试一下能不能传 args"都应该用一个新建的临时页面，或者 dry-run 接口（如果有的话）。

2. **LLM 在 inline 工具调用 args 包含大字符串时会丢失字段。** 实测在这个环境下：
 - ~50 字符 content：OK
 - ~200 字符 content：OK
 - ~17,000 字符 content：args 整体丢失，position 69 错误
 - 阈值大约在 1k–2k 字符之间（未精确测）
 这是 LLM 输出 token 时的硬限制，不是 MCP 工具问题。**超阈值的内容同步必须改走"用户手工粘贴"或"用户运行脚本"路径，不要在生产对象上反复试错。**

3. **紧急止血优先于完整恢复。** 当生产数据被破坏、自动恢复路径还不确定能跑通时，第一动作应该是：
 - 提交一个**明确告知"这是异常状态、恢复中"**的占位内容
 - 把恢复操作交给用户/Confluence UI 自带的版本回滚
 - 不要继续在原页面上反复试错（每次试错失败都浪费时间，但页面始终处于错误状态）

4. **MCP 写入工具的"测试模式"应该是新建临时对象。** 验证 args 传递、字段格式、API 行为，正确做法是 `create_page` 一个 `__test_sandbox__` 页面、在它上面操作，验证完 `delete_page` 销毁。绝不在目标页面上验证。

## Triggers

- "test 一下能不能写"
- "试一下 MCP 工具"
- "覆盖了页面"
- "Confluence update 错误"
- "args 字段丢失"
- "position 69"
- "长字符串工具调用"
- "inline 提交大内容"
- "MCP 写入误操作"
- "生产数据回滚"

## 提炼

- → 原则：`各角色目录/AI工程/原则/写入工具不要在生产对象上做test.md`
- → 原则：`各角色目录/AI工程/原则/LLM工具调用args超阈值会丢失.md`
