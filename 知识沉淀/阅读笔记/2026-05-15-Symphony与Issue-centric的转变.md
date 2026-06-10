---
title: "Symphony 与 Issue-centric 的转变：Harness Engineering 的实战延伸"
author: "Ryan Lopopolo（OpenAI）/ Alex / Latent Space 播客 / OpenAI Blog"
platform: "OpenAI Blog + Latent Space 播客 + Symphony SPEC.md + 内部分享"
date: 2026-04
url: "https://openai.com/index/open-source-codex-orchestration-symphony/"
read_date: 2026-05-15
tags: [Harness Engineering, Symphony, Issue-centric, Ralph Loop, Ghost Library, AI Agent, OpenAI]
related:
  - "阅读笔记/2026-04-05-Harness-Engineering的本质.md"
---

# Symphony 与 Issue-centric 的转变

> 这篇是 [`2026-04-05-Harness-Engineering的本质.md`](./2026-04-05-Harness-Engineering的本质.md) 的实战延伸。4-05 那篇是 PM 视角的概念入门（Harness 是什么、五大组件），这篇是 OpenAI 团队 5 个月真实跑下来的实战延伸 + 下一代演化（从 session 到 issue）。
>
> 不重复概念部分。只记本次阅读相对 4-05 的 **delta**。

## 阅读材料

- OpenAI 官方：<https://openai.com/index/open-source-codex-orchestration-symphony/>
- Latent Space 播客 90 min：Ryan Lopopolo 详细访谈
- Symphony SPEC.md：<https://github.com/openai/symphony/blob/main/SPEC.md>
- 内部分享转写：集体学习 0515.md

## 一句话总结

**Harness Engineering 让 agent 能可靠写代码，Symphony 让 agent 摆脱"人盯 session"的瓶颈——把工作单位从 session 升级到 issue。**

## Delta 1：从 What 到 How，有了实战数据

4-05 那篇讲了"Harness 是 80% 的因素"，但没有数据支撑。这次有了：

| 数据点 | 数值 | 含义 |
|---|---|---|
| 团队规模 | 3 → 7 工程师 | 不写代码，全交给 Codex |
| 周期 | 2025-08 启动 → 2026-04 开源 | 5 个月 |
| 产出 | ~100 万行代码 / ~1500 PR | 真实生产 frontier 产品 |
| 单人吞吐 | 3.5 PR/天（5.2 时代）→ 5-10 PR/天（5.3 时代） | 加人后还在涨（反 Brooks's Law） |
| 用户 | 数百内部日活 | 不是 demo |
| 比手写快 | ~10 倍（Ryan 估计） | |

**反 Brooks's Law 的解释**：新 agent 不需要传统 onboarding——repo 里的 docs/tests/structure 本身就是 harness，agent 通过 in-context learning 直接开工。**当代码库本身是 harness 时，加 agent ≈ 加并行度，没有协调成本。**

## Delta 2：瓶颈从「模型」转移到「人的注意力」

4-05 笔记隐含了一个假设：harness 做好了，问题就解决了。但实战发现：

> 「管 3-5 个 Codex session 已经把我榨干了。」—— Ryan

**Codex 5.2 发布后吞吐翻倍，人的注意力反而成了新瓶颈。** 这是 4-05 笔记没覆盖的。

解法不是"再优化 harness"，而是**升级工作单元**——从 session 转向 issue：

| 维度 | Session-centric（今天大多数人） | Issue-centric（Symphony） |
|---|---|---|
| 触发 | 人打开 session 输入 prompt | tracker 出现 issue |
| 生命周期 | terminal 关了就没了 | 直到 issue 解决 |
| 恢复 | 人手动重启 | 自动 retry |
| 并行度上限 | 人类注意力 | compute budget |
| 上下文 | 每次人重新解释 | 持久存在 issue 描述里 |

**核心口号**：manage work, not agents.

## Delta 3：Symphony 本身的演化路径

V1 (tmux 版) → V2 (内部工具) → V3 (开源 SPEC.md)。

**这是任何新工具/新方法论的正确演化路径**：

1. 粗糙版本（哪怕用 tmux + bash）先证明想法成立
2. 内部强耦合快速迭代
3. 成熟后再抽 spec / 开源

不要倒过来：先抽象 → 再用。**抽象先于使用一定会过度设计。**

## Delta 4：Ghost Library + Ralph Loop（spec 优先于代码）

这是这篇文章最反直觉、最有迁移价值的概念。

**Ghost Library**：开源不发包，发 SPEC.md。你的 agent 读 spec，按你的语言/风格从头实现。验证方法：同一份 SPEC 被 6 种语言（Elixir/TS/Go/Rust/Java/Python）各自一次性 fresh 实现成功。

**Ralph Loop**：

```
Agent A 读运行中的系统 → 写出描述行为的 spec
Agent B 在干净环境只看 spec → 实现一份
Agent C 比较实现与原系统 → 找差距 → 更新 spec
循环，直到 fresh 实现能足够忠实复现
```

**核心判据**：spec 写得够清楚 ⇔ fresh agent 能从 spec 重建系统。

**SPEC 用 RFC 2119 语言**（MUST/SHOULD/MAY）。给 agent 看的文档必须比给人看的文档更明确——agent 不能靠默契推断意图。

→ 已独立沉淀为：[`各角色目录/AI工程/原则/2026-05-15-给Agent看的spec要用RFC2119风格.md`](../各角色目录/AI工程/原则/2026-05-15-给Agent看的spec要用RFC2119风格.md)

## Delta 5：Agent 学环境，不学指令

> 「Agent 会复制 repo 里已有的模式，包括坏模式。只要一个文件写得差，一周之内 agent 会把这个坏模式复制得到处都是。」

**对 prompt engineering 的颠覆**：你 prompt 写得再好，agent 推开门看到一堆坏代码，它会模仿坏代码。这个判断对 AI 销售也成立——agent 学的是 case 库 / 话术库 / 历史会话的整体气质，不是你 system prompt 里写的几条规则。

→ 已独立沉淀为：[`各角色目录/AI工程/洞察/2026-05-15-Agent学的是环境不是指令.md`](../各角色目录/AI工程/洞察/2026-05-15-Agent学的是环境不是指令.md)

## Delta 6：Explore mode vs Execute mode

把 agent 工作分两种：

- **Explore**：我还在思考问题，agent 的回答会激发新想法，交互本身就是价值 → 本地 interactive session
- **Execute**：要做什么已经清楚，只需要完成 → Symphony-like 自主跑

Symphony 只瞄准 execute mode。**这不只是 agent 的事，本质上是「人的工作粒度」问题——什么东西值得变成稳定的 work item，什么东西还应该停留在探索对话里。**

对应到我们工作：
- 调研 / 方案讨论 / 复盘 → Explore（chat 模式）
- PRD 写完后的执行 / 数据拉取 / 文档同步 / case 标注 → Execute（脚本 / skill / 工作流）

## 留口待用的其他观点（暂不独立沉淀）

这些观点很好，但我现在缺乏可立刻应用的场景，先记录在此，遇到合适场景再独立成原则/洞察。

| 观点 | 一句话 | 触发时机（什么时候独立成则） |
|---|---|---|
| **Binary Review** | PR / 方案要么原样合，要么整段重写。10 分钟重生成 < 30 分钟修补 | 当我开始让 agent 大量产出方案/代码、出现"边改边修"的 loop 时 |
| **Skill Distillation** | 周期跑 agent 分析所有 session logs，找"反复踩的坑" → 推回 repo | 当我们的知识沉淀进入"自动发现"阶段（手工沉淀已经跟不上） |
| **6 个 skill 就够** | 能不扩就不扩，先想"能不能塞进已有的" | 当 skill 数量超过 ~10 个，开始出现"agent 选错 skill"的现象时 |
| **Linter as Teaching** | lint 错误信息本身要包含修复说明，给 AI 看不只给人看 | 当我们开始为 AI 写"诊断信息"型文档时 |
| **agent-to-agent 霸凌** | reviewer agent 说什么 author agent 都改，永远收敛不了。社会默契要显式写出 | 当我们引入 agent 互审 / 多 agent 协作时 |
| **"agent 每次犯的错，都是某个还没写下来的非功能性需求"** | 这是一个非常本质的判断，可以重新组织"AI 销售出错的归因方式" | 当我们做 AI 销售失败 case 复盘 v2 时 |
| **Doc-Gardening Agent** | 定期跑 agent 对照文档与真实代码，不一致就开 PR 修文档 | 当我们的 PRD / 知识库出现"文档腐烂"的真实痛点时 |

## 对 PM 的新增意义（相对 4-05）

4-05 的结论：「PM 能做的 = 前两层（Prompt + Context）」

**这次的新结论**：PM 还能做第三层的两件事，比 prompt/context 杠杆更大：

1. **写 RFC 2119 风格的 spec**：把"对/错"的判据写到可以被 agent 自动校验的程度。这是 PM 的核心活——把模糊需求翻译成精确 spec，本来就是产品工作的本质，只是过去翻译给人，现在要翻译给 agent。

2. **管 issue，不管 agent**：把工作单元从"我让 AI 做这个 prompt"升级为"这个 issue 需要被解决"。issue 是组织记忆，session 是临时火花。我应该把更多东西沉淀成 issue 而不是 session。

> Humans steer. Agents execute.
>
> 在 5-15 这个时间点，steer 的核心动作是**写 spec + 管 issue**。
