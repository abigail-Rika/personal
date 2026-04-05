---
title: "Harness Engineering 的本质是什么"
author: "riba2534（知乎）/ harness-engineering.ai"
platform: 知乎 + harness-engineering.ai
date: 2026-03
url: "https://www.zhihu.com/question/2016648624256340425/answer/2017950264284436048"
read_date: 2026-04-05
tags: [Harness Engineering, Context Engineering, AI Agent, 生产可靠性]
---

# Harness Engineering 的本质

## 一句话

AI 模型是一匹能力强但不可控的马，Harness（马具）= 缰绳 + 鞍具 + 围栏——让它朝正确方向跑、不跑偏、跑歪了能拉回来的整套控制基础设施。

## 三层概念关系

```
Prompt Engineering（写好指令）
  ⊂ Context Engineering（管好信息）
    ⊂ Harness Engineering（管好整个系统）
```

| 层级 | 管什么 | PM 类比 | 对可靠性影响 |
|------|--------|---------|------------|
| Prompt Engineering | 一次对话怎么说清楚 | 给研发发一条消息 | 5-15% |
| Context Engineering | AI 每一步看到的全部信息 | 给研发建完整需求文档 + 背景资料 | 15-30% |
| Harness Engineering | 模型周围的一切 | 需求文档 + code review + 测试 + 上线审批 + 监控 | 50-80% |

核心论断：换模型只影响 10-15%，换控制系统决定能不能用。**Harness 是 80% 的因素。**

## 五个核心组件

### 1. Context Engineering（给对信息）
AI 每一步该看到什么信息——不是全塞进去，是精准给当前步骤需要的。

案例：Vercel 把 Agent 可用工具从 15 个减到 2 个，准确率 80% → 100%，速度快 3.5 倍。信息越纯净，AI 越聪明。

### 2. Tool Orchestration（管好工具）
AI 能用哪些工具、怎么用、用错了怎么办。定义权限边界和错误处理。

### 3. Verification Loops（每步检查）——ROI 最高
AI 每做完一步，自动检查结果对不对，再进行下一步。任务完成率从 83% 涨到 96%，不用换模型。

### 4. Cost Envelope（成本围栏）
给每个任务设成本上限，超了自动停。案例：Agent 遇到上游数据错误重试 340 次，6 小时烧 2400 美元（日常 180 美元）。

### 5. Observability（可观测性）
AI 做了什么、为什么做、每步结果，全部结构化记录，出问题能回溯。

## 关键案例

| 公司 | 做了什么 | 结果 |
|------|---------|------|
| LangChain | 只优化 Harness，模型不变 | 任务完成率 52.8% → 66.5% |
| Vercel | 工具从 15 减到 2 | 准确率 80% → 100%，token -37% |
| Manus | KV-cache 优化 + Context 管理 | 成本降低 10 倍 |
| OpenAI Codex | 沙箱 + 验证循环 + 结构化工具 | 3 个工程师 5 个月生成 100 万行代码 |

## 对 PM 的意义

1. **模型不是瓶颈，模型周围的系统才是。** 和「Agent 落地不佳五大问题」结论一致。
2. **PM 能做的 = 前两层（Prompt + Context）。** Harness 的第三层主要是工程团队的事，但 PM 需要知道它的存在——当 Agent 产品上线不稳定时，答案大概率在这一层。
3. **进化路线是 Prompt → Context → Harness。** 分享讲的是 PM 从第一阶段到第二阶段的跃迁。Harness 是更完整的全景图。
