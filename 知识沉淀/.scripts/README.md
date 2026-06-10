# 知识沉淀脚本

## build_index.py

扫所有沉淀文件 `各角色目录/<角色>/{经验,技能,原则,洞察}/*.md` 的 YAML front matter，
按角色 + 类型聚合，生成索引并替换：

- `知识索引.md` 中 `<!-- AUTO:BEGIN role-index:<角色> -->...<!-- AUTO:END -->` 块
- `各角色目录/<角色>/角色说明.md` 中 `<!-- AUTO:BEGIN role-knowledge:<角色> -->...<!-- AUTO:END -->` 块
- `~/.cursor/rules/知识索引.mdc` 中 `<!-- AUTO:BEGIN requestable-role-index:<角色> -->...<!-- AUTO:END -->` 块（如果文件存在）

### 用法

```bash
# 重建索引（实际写入）
python3 知识沉淀/.scripts/build_index.py

# 只看会改什么，不实际写入
python3 知识沉淀/.scripts/build_index.py --dry-run

# CI 模式：有漂移时退出码 1
python3 知识沉淀/.scripts/build_index.py --check

# 只更新知识库内索引，不更新 Cursor rule
python3 知识沉淀/.scripts/build_index.py --no-cursor-rule
```

### 数据契约

所有沉淀文件**必须**有 `description` 字段：

```yaml
---
description: "1-2 句话描述，用于索引"
---
```

所有沉淀条目文件名必须以 `YYYY-MM-DD-` 开头，包括经验、技能、原则、洞察、技术文章、阅读笔记。

技能/原则/洞察 额外可有 `triggers` / `source` 字段（仅供人工 grep，脚本不读）。

经验会在索引里自动加日期前缀并按时间倒序。

### 反模式

- ❌ 手工修改 AUTO 块内容（下次跑脚本会被覆盖）
- ❌ 多行字符串值（脚本只解析单行 `key: value`）
- ✅ 改描述就改文件自身的 `description` 字段，然后跑脚本

## migrate_experience_frontmatter.py

一次性迁移工具。从 `知识索引.md` 反向抓经验描述写回经验文件 front matter。
首次启用 build_index 时已经跑过，**新沉淀不需要再用**。
