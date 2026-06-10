#!/usr/bin/env python3
"""一次性迁移：把 知识索引.md 里已经写好的经验描述，反向写回经验文件的 front matter。

用法：
  python3 migrate_experience_frontmatter.py --dry-run     # 只打印不写
  python3 migrate_experience_frontmatter.py               # 实际写入
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 知识沉淀/
INDEX = ROOT / "知识索引.md"

# 命中类似：- `各角色目录/产品设计/经验/2026-03-31-异形弹窗方案演变.md` — 描述...
LINE_RE = re.compile(
    r"`各角色目录/([^/]+)/经验/([^`]+\.md)`\s*[—\-–]\s*(.+?)\s*$"
)


def extract_descriptions() -> dict[tuple[str, str], str]:
    desc_map: dict[tuple[str, str], str] = {}
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.search(line.strip())
        if not m:
            continue
        role, fn, desc = m.group(1), m.group(2), m.group(3)
        # 同一文件可能在角色索引里出现一次；以第一次为准
        desc_map.setdefault((role, fn), desc.strip())
    return desc_map


def has_front_matter(text: str) -> bool:
    return text.lstrip().startswith("---")


def build_front_matter(desc: str) -> str:
    # 用 YAML 的字符串字面量，转义内部双引号
    safe = desc.replace("\\", "\\\\").replace('"', '\\"')
    return f'---\ndescription: "{safe}"\n---\n\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    desc_map = extract_descriptions()
    print(f"从 知识索引.md 抓到 {len(desc_map)} 条经验描述\n")

    changed = 0
    skipped_has_fm = 0
    missing_files = []
    missing_desc = []

    role_dirs = (ROOT / "各角色目录").iterdir()
    all_experience_files: list[tuple[str, Path]] = []
    for role_dir in role_dirs:
        if not role_dir.is_dir():
            continue
        exp_dir = role_dir / "经验"
        if not exp_dir.exists():
            continue
        for f in sorted(exp_dir.glob("*.md")):
            all_experience_files.append((role_dir.name, f))

    print(f"扫到经验文件 {len(all_experience_files)} 个\n")

    for role, fp in all_experience_files:
        key = (role, fp.name)
        desc = desc_map.get(key)
        text = fp.read_text(encoding="utf-8")

        if has_front_matter(text):
            skipped_has_fm += 1
            print(f"  [SKIP-已有FM] {role}/经验/{fp.name}")
            continue

        if not desc:
            missing_desc.append(f"{role}/经验/{fp.name}")
            print(f"  [MISS-无描述] {role}/经验/{fp.name}")
            continue

        new_text = build_front_matter(desc) + text
        if args.dry_run:
            print(f"  [WOULD-WRITE] {role}/经验/{fp.name}")
            print(f"    description: \"{desc[:60]}{'...' if len(desc) > 60 else ''}\"")
        else:
            fp.write_text(new_text, encoding="utf-8")
            print(f"  [WROTE] {role}/经验/{fp.name}")
        changed += 1

    print(f"\n=== 汇总 ===")
    print(f"待改: {changed}")
    print(f"已有 front matter（跳过）: {skipped_has_fm}")
    print(f"知识索引里没找到描述: {len(missing_desc)}")
    if missing_desc:
        for x in missing_desc:
            print(f"  - {x}")
    if missing_files:
        for x in missing_files:
            print(f"  - {x}")
    if args.dry_run:
        print("\n(dry-run，未写入。去掉 --dry-run 实际执行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
