# Agent 知识工程实践：让 Coding Agent 像人一样学习、记忆和成长

- **来源**：[知乎专栏 - stonepage](https://zhuanlan.zhihu.com/p/2013979334365434808)
- **作者**：stonepage（通讯作者：@tennyzhuang）
- **发布时间**：2026-03-16
- **归档时间**：2026-03-26
- **示例仓库**：[agent-knowledge-framework](https://github.com/st1page/agent-knowledge-framework)

---

## 核心观点

> agent 不是菜，他只是不知道。

Agent 产出和预期有偏差，根本原因不是能力不够，而是缺少关于你的项目、团队、偏好的上下文知识。Prompt Engineering 优化的是单次对话的表达效率，Knowledge Engineering 解决的是 agent 的认知基础——前者是战术，后者是战略。

## 一、知识从哪来？——让 agent 像人一样学习

### 1. 复盘旧知：反思沉淀

每次人机交互结束后，让 agent 把重要的东西沉淀下来（如写入 AGENTS.md）。更进一步，可以追问 agent："你刚才为什么没有 xxx？"——让他暴露认知盲区，然后补充完整。

### 2. 对标他方：学习借鉴

不要自己搜到答案再喂给 agent。直接让 agent 去读原始材料（博客、成熟项目、PR），自己消化过的东西比被告知的更扎实。

关键不是让 agent "知道某个概念是什么"（训练数据里有），而是让他**在你的项目语境下重新理解**——哪些场景适用、边界在哪、和现有做法怎么衔接。

### 3. 沙盒演练：模拟试错

对于训练数据里完全没有的内部工具，让 agent 自己去玩——提交各种 case、排查运行情况、总结为 skill。这是 agent 相比纯 LLM 的核心优势：能实际运行、观察输出、根据反馈调整。

### 关键认知

> 知识的具体内容应该让 agent 自己来写，而不是人替他写。agent 比人更知道自己需要记住什么——因为他是读者。

## 二、知识怎么存？——Persistent Memory

### 四种载体

| 载体 | 特点 | 适用场景 |
|---|---|---|
| **AGENTS.md / CLAUDE.md** | 随项目走，始终在 context 里，必须精简 | "做错一次就不可逆"的规则 |
| **独立知识库** | 结构化、可检索、可演进，跨项目复用 | 跨项目通用能力（git 协作规范、PR 工作流等） |
| **既有载体**（代码/文档/PR） | 不需额外维护，但要有意识让产出承载知识 | PR 描述写清"为什么这么改" |
| **人机协作**（Notion/IM/Wiki） | 接入团队已有知识网络 | 让 agent 读搜 Notion、在 IM 汇报进展 |

### 独立知识库的内部结构：两个正交维度

**横切——按类型（五分法）：**

| 类型 | 回答的问题 | 示例 |
|---|---|---|
| **experience** | 发生了什么？ | workflow run 失败排查记录 |
| **skill** | 下次怎么操作？ | 跨层 API 重构的分层修改顺序 |
| **principle** | 应该/不应该做什么？ | 每个功能用独立 worktree |
| **insight** | 为什么会这样？ | 迭代式 review 比一次性修复更可靠 |
| **question** | known unknown | 这个行为是否总是成立？ |

生成关系：`question → experience → skill / principle / insight`

**为什么没有 Fact？** fact 会过时但没有自然更新机制。experience 天然带时间戳，旧记录会自然引发验证。单独维护 fact 是在制造定时炸弹。

**竖切——按角色（role）：**

- `base/`：跨角色通用知识（git worktree、凭证安全）
- `roles/<role>/`：各角色专有知识（含 AGENTS.md 角色描述 + 知识索引）

判断标准不是"多个角色都有用就放 base"——同一个工具，不同角色 learn 出的 skill 完全不同。base 只放真正与角色视角无关的知识。

角色划分会随知识库增长而动态演化：分裂、合并、互相学习、自我修订。

## 三、怎么维护？——让知识保持活性

### 1. 反馈闭环

犯错 → 追问为什么 → 发现是知识缺失/不够具体/加载时机不对 → agent 自己改进知识。

### 2. 元认知

"怎么沉淀知识"这件事本身就需要被沉淀（`knowledge-sedimentation.md`）。元认知三个层面：
- 怎么沉淀（分类、提炼、判断放哪）
- 什么时候沉淀（触发场景列表）
- 反思的意识（主动问自己四个问题）

### 3. Comment 机制

在 experience 文件末尾添加后续关联，形成 experience 之间、experience 与 insight/principle 之间的双向链接。comment 是批注和索引，不是正文。

### 4. Dreaming（夜间巡检）

设 `maintainer` 角色定期巡检：
- **机械层（linter）**：坏链接、索引缺口、近似重复——自动执行
- **语义层（synthesis）**：跨角色关联、可归纳 insight、过时信息——只输出候选，人来决策

夜间还可复盘白天新增的 experience，设计最小实验验证假设。

## 四、Agent 怎么读？——Context Engineering

不是把所有知识塞进 context，而是按需加载最相关的。不相关的知识会**污染**判断。

### 分层加载

| 层级 | 内容 | 加载时机 |
|---|---|---|
| **常驻** | AGENTS.md + roles/<role>/AGENTS.md | 每次任务 |
| **按需** | skill / principle / insight / experience | 通过索引命中后 |
| **触发式** | 凭证安全、worktree 规范等 | 特定场景自动提醒 |

### Trigger 机制（两层过滤）

1. **AGENTS.md 摘要**（常驻、轻量）：关键词粗筛
2. **文档 front matter triggers**（按需、精确）：精筛确认

### 联想：从一条知识到一片知识

- 纵向连接（提炼链）：experience → skill/principle/insight
- 横向连接（comment 网络）：experience 之间的关联
- 索引连接：AGENTS.md 摘要中的关键词自然关联

### Context 压缩后的恢复

长 session 中 context 被压缩后，重新读 AGENTS.md + 角色 AGENTS.md 即可恢复，这也是为什么这两份文件必须精简。

## 结语

> 知识工程没有完成的那一天。重要的不是一开始就设计出完美的体系，而是先让 agent 开始记，然后让体系在记的过程中自己长出来。

整套体系不依赖数据库、向量检索或复杂 pipeline——核心就是目录结构加 Markdown，agent 用 grep 就能搜索。这种简单性是它能持续运转的关键。
