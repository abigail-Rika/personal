#!/usr/bin/env python3
"""把通话 JSON 转成可读 markdown：合并相邻同角色短句、加时间戳"""
import json, sys, os, re

def ms_to_mmss(ms):
    s = int(ms) // 1000
    return f"{s//60:02d}:{s%60:02d}"

def role(t):
    return "销售" if t == "teacher" else "家长"

def fmt(src):
    data = json.load(open(src))
    out_lines = []
    cur_role = None
    cur_text = []
    cur_start = None
    cur_end = None
    for seg in data:
        r = role(seg.get("identityType", ""))
        t = seg.get("text", "").strip()
        if not t:
            continue
        st = int(seg["startTime"])
        et = int(seg["endTime"])
        if r == cur_role and (st - (cur_end or st)) < 3000:
            cur_text.append(t)
            cur_end = et
        else:
            if cur_role is not None:
                out_lines.append(f"[{ms_to_mmss(cur_start)}] **{cur_role}**：{' '.join(cur_text)}")
            cur_role = r
            cur_text = [t]
            cur_start = st
            cur_end = et
    if cur_role is not None:
        out_lines.append(f"[{ms_to_mmss(cur_start)}] **{cur_role}**：{' '.join(cur_text)}")
    return "\n\n".join(out_lines)

if __name__ == "__main__":
    for src in sys.argv[1:]:
        dst = re.sub(r"\.json$", ".md", src)
        md = fmt(src)
        open(dst, "w").write(f"# {os.path.basename(dst)}\n\n{md}\n")
        print(f"{dst}: {len(md.split(chr(10)))} 行")
