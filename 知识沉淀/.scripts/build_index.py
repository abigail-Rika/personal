#!/usr/bin/env python3
"""索引生成器。

扫所有沉淀文件的 YAML front matter（description 字段），按角色 + 类型聚合，
生成索引片段并替换：
  - 知识索引.md 里每个角色 "知识索引" 块
  - 各角色目录/<角色>/角色说明.md 里 "知识索引" 块
  - ~/.cursor/rules/知识索引.mdc 里每个角色 "已有知识" 块（如果存在）

使用 HTML 注释做替换锚点：
  <!-- AUTO:BEGIN role-index:产品设计 -->
  ... 自动生成 ...
  <!-- AUTO:END role-index:产品设计 -->

用法：
  python3 build_index.py --dry-run        # 只打印差异
  python3 build_index.py                  # 实际写入
  python3 build_index.py --check          # CI 模式：检测漂移，有漂移 exit 1
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLES_DIR = ROOT / "各角色目录"
INDEX_FILE = ROOT / "知识索引.md"
CURSOR_RULE_INDEX_FILE = Path.home() / ".cursor" / "rules" / "知识索引.mdc"

KIND_ORDER = ["经验", "技能", "原则", "洞察"]
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


@dataclass
class Entry:
    role: str
    kind: str
    filename: str
    description: str
    date: str | None  # 所有沉淀条目都应从文件名前缀解析到日期

    @property
    def rel_in_role(self) -> str:
        """角色说明.md 里用的相对路径"""
        return f"{self.kind}/{self.filename}"

    @property
    def rel_in_root(self) -> str:
        """知识索引.md 里用的相对路径"""
        return f"各角色目录/{self.role}/{self.kind}/{self.filename}"

    @property
    def rel_in_personal(self) -> str:
        """Cursor rule 里用的工作区相对路径"""
        return f"personal/知识沉淀/{self.rel_in_root}"


def _unescape_yaml_double_quoted(s: str) -> str:
    """处理 YAML double-quoted string 里的转义：\\" -> "，\\\\ -> \\"""
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == '"':
                out.append('"')
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_front_matter(text: str) -> dict[str, str]:
    """超简 YAML front matter 解析。只取顶层 key: "value" 形式。"""
    if not text.lstrip().startswith("---"):
        return {}
    stripped = text.lstrip()
    end = stripped.find("\n---", 3)
    if end == -1:
        return {}
    fm = stripped[3:end].strip()
    result: dict[str, str] = {}
    current_key: str | None = None
    for line in fm.splitlines():
        m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)$', line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val and val[0] == '"' and val[-1] == '"' and len(val) >= 2:
                val = _unescape_yaml_double_quoted(val[1:-1])
            elif val and val[0] == "'" and val[-1] == "'" and len(val) >= 2:
                val = val[1:-1].replace("''", "'")
            result[key] = val
            current_key = key
        elif current_key and line.startswith("  "):
            # list / 续行 暂不解析
            pass
    return result


def scan_entries() -> list[Entry]:
    entries: list[Entry] = []
    for role_dir in sorted(ROLES_DIR.iterdir()):
        if not role_dir.is_dir():
            continue
        role = role_dir.name
        for kind in KIND_ORDER:
            kind_dir = role_dir / kind
            if not kind_dir.is_dir():
                continue
            for fp in sorted(kind_dir.glob("*.md")):
                fm = parse_front_matter(fp.read_text(encoding="utf-8"))
                desc = fm.get("description", "").strip()
                if not desc:
                    print(
                        f"[WARN] 缺 description: {fp.relative_to(ROOT)}",
                        file=sys.stderr,
                    )
                    desc = "(待补描述)"
                m = DATE_RE.match(fp.stem)
                if not m:
                    print(
                        f"[WARN] 文件名缺日期前缀 YYYY-MM-DD-: {fp.relative_to(ROOT)}",
                        file=sys.stderr,
                    )
                entries.append(
                    Entry(
                        role=role,
                        kind=kind,
                        filename=fp.name,
                        description=desc,
                        date=m.group(1) if m else None,
                    )
                )
    return entries


def render_for_role_doc(role: str, entries: list[Entry]) -> str:
    """生成角色说明.md 内 "知识索引" 区段。"""
    lines: list[str] = []
    by_kind = {k: [e for e in entries if e.role == role and e.kind == k] for k in KIND_ORDER}

    for kind in ["原则", "技能", "洞察"]:
        items = by_kind[kind]
        lines.append(f"### {kind}")
        if not items:
            lines.append("（暂无）")
        else:
            for e in sorted(items, key=lambda x: x.filename):
                lines.append(f"- [`{e.rel_in_role}`]({e.rel_in_role}) — {e.description}")
        lines.append("")

    # 经验按日期倒序
    exp = sorted(by_kind["经验"], key=lambda x: x.date or "", reverse=True)
    lines.append("### 经验（按时间倒序）")
    if not exp:
        lines.append("（暂无）")
    else:
        for e in exp:
            date_prefix = f"{e.date} · " if e.date else ""
            lines.append(f"- {date_prefix}[`{e.rel_in_role}`]({e.rel_in_role}) — {e.description}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_for_root_index(role: str, entries: list[Entry]) -> str:
    """生成 知识索引.md 内某角色的 "知识索引" 列表。"""
    lines: list[str] = []
    by_kind = {k: [e for e in entries if e.role == role and e.kind == k] for k in KIND_ORDER}

    for kind in ["原则", "技能", "洞察"]:
        items = by_kind[kind]
        if items:
            lines.append(f"- {kind}：")
            for e in sorted(items, key=lambda x: x.filename):
                lines.append(f"  - `{e.rel_in_root}` — {e.description}")
        else:
            lines.append(f"- {kind}：（暂无）")

    exp = sorted(by_kind["经验"], key=lambda x: x.date or "", reverse=True)
    if exp:
        lines.append(f"- 经验（按时间倒序）：")
        for e in exp:
            date_prefix = f"{e.date} · " if e.date else ""
            lines.append(f"  - {date_prefix}`{e.rel_in_root}` — {e.description}")
    else:
        lines.append(f"- 经验：（暂无）")

    return "\n".join(lines) + "\n"


def sorted_for_kind(kind: str, items: list[Entry]) -> list[Entry]:
    """索引排序：经验按日期倒序，其余按文件名稳定排序。"""
    if kind == "经验":
        return sorted(items, key=lambda x: x.date or "", reverse=True)
    return sorted(items, key=lambda x: x.filename)


def render_for_cursor_rule(role: str, entries: list[Entry]) -> str:
    """生成 ~/.cursor/rules/知识索引.mdc 内某角色的精简索引。"""
    lines: list[str] = []
    by_kind = {k: [e for e in entries if e.role == role and e.kind == k] for k in KIND_ORDER}

    for kind in ["原则", "技能", "洞察", "经验"]:
        for e in sorted_for_kind(kind, by_kind[kind]):
            date_prefix = f"{e.date} · " if kind == "经验" and e.date else ""
            lines.append(f"- {kind}：{date_prefix}`{e.rel_in_personal}` — {e.description}")

    if not lines:
        lines.append("- 暂无")
    return "\n".join(lines) + "\n"


def replace_auto_block(text: str, block_id: str, new_content: str) -> tuple[str, bool]:
    """替换 <!-- AUTO:BEGIN block_id --> ... <!-- AUTO:END block_id --> 之间的内容。
    返回 (新文本, 是否替换成功)。"""
    begin = f"<!-- AUTO:BEGIN {block_id} -->"
    end = f"<!-- AUTO:END {block_id} -->"
    pattern = re.compile(
        re.escape(begin) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    replacement = f"{begin}\n{new_content.rstrip()}\n{end}"
    new_text, n = pattern.subn(replacement, text)
    return new_text, n > 0


def display_path(path: Path) -> str:
    """打印路径时优先显示知识库相对路径，外部文件显示用户目录相对路径。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        try:
            return "~/" + str(path.relative_to(Path.home()))
        except ValueError:
            return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true", help="CI 模式：有漂移 exit 1")
    parser.add_argument(
        "--no-cursor-rule",
        action="store_true",
        help="不更新 ~/.cursor/rules/知识索引.mdc",
    )
    args = parser.parse_args()

    entries = scan_entries()
    print(f"扫到 {len(entries)} 条沉淀")

    # 统计
    from collections import Counter
    stats = Counter((e.role, e.kind) for e in entries)
    roles = sorted({e.role for e in entries})
    for role in roles:
        line = "  " + role + "：" + "  ".join(
            f"{k} {stats.get((role, k), 0)}" for k in KIND_ORDER
        )
        print(line)
    print()

    targets: list[tuple[Path, str, str]] = []  # (path, block_id, new_content)

    for role in roles:
        role_doc = ROLES_DIR / role / "角色说明.md"
        if role_doc.exists():
            targets.append(
                (role_doc, f"role-knowledge:{role}", render_for_role_doc(role, entries))
            )
        # 在 知识索引.md 里每个角色一个块
        targets.append(
            (INDEX_FILE, f"role-index:{role}", render_for_root_index(role, entries))
        )
        if CURSOR_RULE_INDEX_FILE.exists() and not args.no_cursor_rule:
            targets.append(
                (
                    CURSOR_RULE_INDEX_FILE,
                    f"requestable-role-index:{role}",
                    render_for_cursor_rule(role, entries),
                )
            )

    has_drift = False
    for path, block_id, new_content in targets:
        old = path.read_text(encoding="utf-8")
        new, ok = replace_auto_block(old, block_id, new_content)
        if not ok:
            print(f"[SKIP] 找不到锚点 {block_id} in {display_path(path)}", file=sys.stderr)
            continue
        if new == old:
            continue
        has_drift = True
        if args.check:
            print(f"[DRIFT] {display_path(path)} :: {block_id}")
        elif args.dry_run:
            print(f"[WOULD-UPDATE] {display_path(path)} :: {block_id}")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"[UPDATED] {display_path(path)} :: {block_id}")

    if args.check:
        return 1 if has_drift else 0
    if not has_drift:
        print("无变更，索引已是最新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
