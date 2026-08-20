"""
从 20 通转写中提取家长侧发言，便于人工归类"未到习真实原因"。
按通话渲染：家长发言 + 销售开场关键段，方便快速判断。
"""
import csv
import json
from pathlib import Path

BASE = Path(__file__).parent
TR_DIR = BASE / "transcripts"

with open(BASE / "sample_20.csv") as f:
    rows = list(csv.DictReader(f))

# 按时长排序
rows = sorted(rows, key=lambda r: int(r["duration_s"]))

out = BASE / "parent_voice_for_labelling.md"
with open(out, "w", encoding="utf-8") as f:
    for i, r in enumerate(rows, 1):
        path = TR_DIR / f"u{r['user_id']}_t{r['tutor_ldap']}_d{r['duration_s']}s.json"
        with open(path) as g:
            transcript = json.load(g)
        teacher_segs = [s for s in transcript if s.get("identityType") == "teacher"]
        customer_segs = [s for s in transcript if s.get("identityType") != "teacher"]
        customer_text = " | ".join([s["text"].strip() for s in customer_segs])

        # 销售前 3 段
        teacher_intro = " || ".join([s["text"].strip()[:120] for s in teacher_segs[:3]])

        f.write(f"## {i}. user={r['user_id']} | {r['tutor_ldap']} | {r['duration_s']}s | {r['start_time'] or '时间未知'}\n\n")
        f.write(f"**销售开场（前 3 段）**：\n> {teacher_intro}\n\n")
        f.write(f"**家长全部发言**（{len(customer_segs)} 句，共 {sum(len(s['text']) for s in customer_segs)} 字）：\n")
        for s in customer_segs:
            f.write(f"- {s['text'].strip()}\n")
        f.write("\n---\n\n")

print(f"已生成: {out}")
