# 个人空间

文悦的个人知识管理空间，由 AI 助理协助维护。

## 目录结构

```
personal/
├── work/                    # 工作
│   ├── todos.md             # 待办事项（按紧急重要分类）
│   ├── projects/            # 项目跟踪
│   ├── prd/                 # PRD 相关（writer、review、retro）
│   │   ├── prd-writer/      # PRD 写作 skill
│   │   ├── prd-review/      # PRD 评审 skill
│   │   ├── prd-retro/       # 项目复盘数据回收 skill
│   │   └── 增长产品PRD规范.md
│   ├── scripts/             # 工作自动化脚本（如每日提醒）
│   └── roadmap/             # 周计划、月计划
├── diary/                   # 每日日记（生活为主）
├── reviews/                 # 复盘
│   ├── daily/               # 日复盘（工作为主）
│   ├── weekly/              # 周复盘
│   └── monthly/             # 月复盘
├── knowledge/               # 知识沉淀
│   ├── tech/                # 技术知识
│   ├── product/             # 产品知识
│   └── reading/             # 阅读笔记
├── skills/                  # 技能档案（skill-map.md）
├── thoughts/                # 想法与思考
├── _site/                   # 网站查看器（暂停使用，以后可能恢复）
├── CLAUDE.md                # AI 助理行为规范
└── README.md                # 本文件
```

## 使用方式

在 Cursor 中直接和 AI 对话，说你想记录的内容即可。AI 会自动判断归类并写入对应文件。

## 隐私说明

- `diary/` 和 `thoughts/` 在 .gitignore 中，不进入版本控制
- `_site/` 中的 `.env.local` 也不进入版本控制
