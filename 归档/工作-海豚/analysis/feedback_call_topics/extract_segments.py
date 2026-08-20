"""
从 /tmp/feedback_case.txt 解析 4 个反馈电话 case 的人工标注结构，
按章节统计：对话条数、用户/老师发言条数、估计时长（基于最后一条时间戳-最初一条时间戳）。

每个 case 内的对话格式：
  老师:xxx",起始毫秒结束毫秒（注意没有逗号分隔，是粘连数字串）
  学生:xxx",同上

更准确地说，原文是  `内容",起始endms`，毫秒拼起来。
"""
import re
from pathlib import Path
from collections import defaultdict

SRC = Path("/tmp/feedback_case.txt")

# 标准化主题映射：把所有章节标题映射到 7 个统一主题
TOPIC_MAP = {
    # 1. 开场寒暄
    "开场": "1_开场寒暄",
    "结束关怀": "1_开场寒暄",
    "结束关怀话术": "1_开场寒暄",

    # 2. 学情/学习情况复盘
    "海豚感受-孩子": "2_学情复盘",
    "海豚感受-家长": "2_学情复盘",
    "表扬孩子-询问感受": "2_学情复盘",
    "学情开场": "2_学情复盘",
    "问感受": "2_学情复盘",
    "学情-讲题": "2_学情复盘",
    "学情沟通-家长": "2_学情复盘",
    "表扬孩子": "2_学情复盘",
    "学情简介": "2_学情复盘",
    "学情反馈-妈妈": "2_学情复盘",
    "海豚币": "2_学情复盘",  # 海豚币偏激励，归到学情这边

    # 3. 孩子问题诊断 + 目标对齐
    "学习目标-孩子": "3_问题诊断与目标",
    "问孩子目标": "3_问题诊断与目标",
    "问孩子方案": "3_问题诊断与目标",
    "给出方案": "3_问题诊断与目标",
    "给方案": "3_问题诊断与目标",
    "学习目标-家长/孩子": "3_问题诊断与目标",
    "问孩子目标": "3_问题诊断与目标",
    "问孩子方案": "3_问题诊断与目标",
    "给出解决方案": "3_问题诊断与目标",
    "孩子问题": "3_问题诊断与目标",
    "解决方案": "3_问题诊断与目标",

    # 4. 海豚产品方案/功能介绍
    "海豚方案-家长": "4_产品方案介绍",
    "海豚方案-孩子": "4_产品方案介绍",
    "学习报告": "4_产品方案介绍",
    "学习计划介绍": "4_产品方案介绍",
    "学习计划": "4_产品方案介绍",
    "错题本": "4_产品方案介绍",
    "资料库": "4_产品方案介绍",
    "数学拆解（浏览资料库）": "4_产品方案介绍",
    "拓展提升（数学/物理）": "4_产品方案介绍",
    "学习建议（英语）": "4_产品方案介绍",
    "学习方法": "4_产品方案介绍",
    "学习计划总结": "4_产品方案介绍",
    "微信小程序介绍": "4_产品方案介绍",

    # 5. 长期路径/服务体系
    "助理服务介绍": "5_长期服务路径",
    "约定学习": "5_长期服务路径",

    # 6. 关单/正式会员推销
    "正式会员服务-关单": "6_关单推销",
    "正式会员": "6_关单推销",
    "直通车介绍": "6_关单推销",
    "焦虑": "6_关单推销",
    "焦虑点植入": "6_关单推销",
    "方案": "6_关单推销",
    "关单": "6_关单推销",
    "退费关单": "6_关单推销",
    "会员内容介绍": "6_关单推销",

    # 7. 顾虑承接/问题解答
    "问题解答": "7_顾虑承接",
    "问题解答-家长": "7_顾虑承接",
}


def parse_doc():
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    cases = {}  # case_id -> { 'title': str, 'segments': [(level1, level2_or_None, [对话行])] }

    cur_case = None
    cur_l1 = None  # 一级章节
    cur_l2 = None  # 二级章节（如果有）
    # 一级章节是 \t• \t<标题>; 二级是 \t• \t<标题> 但跟随在一级下面、且名字属于 L2 列表
    # 但实际上无法纯结构区分，只能基于位置。简单做法：所有"\t• \t<title>"行都视作章节边界，
    # 章节内的内容直到下一个章节为止

    case_re = re.compile(r"^case(\d+):链接\s*$")
    # 章节边界：兼容 "\t•\t标题" / "•\t标题" / "数字.标题"（case3 里出现 2.学情反馈-孩子）
    sec_re_bullet = re.compile(r"^\s*[•·]\s*\t?(.+?)\s*$")
    sec_re_num = re.compile(r"^\s*\d+\.([^\d].+)\s*$")  # 必须避免误把对话开头的数字行当章节

    cur_section_lines = []
    cur_section_name = None

    def flush_section():
        nonlocal cur_section_lines, cur_section_name
        if cur_case is None or cur_section_name is None:
            cur_section_lines = []
            cur_section_name = None
            return
        cases[cur_case]["segments"].append({
            "section": cur_section_name,
            "lines": cur_section_lines,
        })
        cur_section_lines = []

    for raw in lines:
        m = case_re.match(raw.strip())
        if m:
            flush_section()
            cur_case = f"case{m.group(1)}"
            if cur_case not in cases:
                cases[cur_case] = {"segments": []}
            cur_section_name = None
            continue

        # 对话行优先（因为对话行可能也以数字结尾）
        if raw.startswith("老师:") or raw.startswith("学生:"):
            if cur_section_name is None:
                # 没有 case 上下文之前的对话忽略
                continue
            cur_section_lines.append(raw)
            continue

        # 章节边界判定：bullet 优先
        m = sec_re_bullet.match(raw)
        if m:
            flush_section()
            cur_section_name = m.group(1).strip()
            continue
        # 数字章节（case3/4 部分章节用 1.开场 / 2.学情反馈-孩子 格式）
        m = sec_re_num.match(raw)
        if m and cur_case is not None:
            flush_section()
            cur_section_name = m.group(1).strip()
            continue

    flush_section()
    return cases


def parse_line_ts(s: str):
    """从一行对话里抽出 (speaker, content, start_ms, end_ms)
    兼容两种格式：
      A) 老师:内容",起始结束        (case1/case2)
      B) 老师:内容结束 + 起始结束    (case3/case4，无 "," 分隔)
    """
    if ":" not in s:
        return None
    speaker, rest = s.split(":", 1)

    # 抓尾部所有数字
    m = re.search(r"(\d+)\s*$", rest.rstrip())
    if m is None:
        return None
    nums = m.group(1)
    content = rest[: m.start()]
    # 去掉末尾的 ",
    content = content.rstrip().rstrip(',').rstrip('"').rstrip()

    if not nums.isdigit():
        return None
    n = len(nums)
    best = None
    for split in range(1, n):
        a = nums[:split]
        b = nums[split:]
        if not a or not b:
            continue
        # 不允许前导 0 长度过怪
        ia = int(a)
        ib = int(b)
        if ib < ia:
            continue
        if ib - ia > 120_000:  # 单句最多 2 分钟
            continue
        # 选最早的合法切分
        best = (ia, ib)
        break
    if best is None:
        # 兜底：当作 start=0, end=int(nums)
        try:
            ib = int(nums)
            best = (0, ib)
        except Exception:
            return None
    return (speaker, content, best[0], best[1])


def analyze():
    cases = parse_doc()
    print(f"解析到 case 数: {len(cases)}\n")
    case_meta = {
        "case1": {"name": "成熟李浩", "tier": "top",  "conv": 25.78, "fb_conv": 65.91, "score": 9.5},
        "case2": {"name": "萌新李浩", "tier": "新老师", "conv": 12.18, "fb_conv": 39.53, "score": None},
        "case3": {"name": "林德徐",   "tier": "top",  "conv": 22.56, "fb_conv": 53.70, "score": None},
        "case4": {"name": "张博文",   "tier": "一般", "conv": 20.13, "fb_conv": 55.56, "score": None},
    }

    # 每个 case 的总时长 + 每章节时长占比
    case_rollup = {}
    topic_dur_by_case = defaultdict(lambda: defaultdict(int))   # case -> topic -> ms
    topic_lines_by_case = defaultdict(lambda: defaultdict(int)) # case -> topic -> count

    for cid, info in cases.items():
        total_ms = 0
        for seg in info["segments"]:
            sec = seg["section"]
            topic = TOPIC_MAP.get(sec)
            if topic is None:
                # 兼容: 把未映射的章节归到 "其他"
                topic = f"其他({sec})"
            # 计算章节用时（基于本章节内对话的 max(end_ms) - min(start_ms)）
            starts, ends = [], []
            for ln in seg["lines"]:
                p = parse_line_ts(ln)
                if p is None:
                    continue
                starts.append(p[2])
                ends.append(p[3])
            if starts and ends:
                seg_ms = max(ends) - min(starts)
                if seg_ms < 0:
                    seg_ms = 0
            else:
                seg_ms = 0
            topic_dur_by_case[cid][topic] += seg_ms
            topic_lines_by_case[cid][topic] += len(seg["lines"])
            total_ms += seg_ms
        case_rollup[cid] = total_ms

    # 输出
    print("=" * 80)
    print("一、每个 case 各主题时长占比（基于章节内时间戳）")
    print("=" * 80)
    for cid in sorted(cases.keys()):
        meta = case_meta.get(cid, {})
        total = case_rollup.get(cid, 0)
        print(f"\n【{cid}】{meta.get('name','?')} / {meta.get('tier','?')} / 老师4期转化率 {meta.get('conv','?')}% / 反馈转化率 {meta.get('fb_conv','?')}%")
        print(f"  总时长（章节累计）: {total/60000:.1f} 分钟")
        items = sorted(topic_dur_by_case[cid].items(), key=lambda kv: -kv[1])
        for topic, ms in items:
            pct = (ms / total * 100) if total else 0
            lines = topic_lines_by_case[cid][topic]
            print(f"    {topic:<22} {ms/60000:>5.1f} min  ({pct:>5.1f}%)  共 {lines} 句")

    # 跨 case 汇总
    print("\n" + "=" * 80)
    print("二、4 个 case 汇总：主题平均时长占比")
    print("=" * 80)
    agg_dur = defaultdict(int)
    grand_total = 0
    for cid in cases:
        for topic, ms in topic_dur_by_case[cid].items():
            agg_dur[topic] += ms
            grand_total += ms

    rows = sorted(agg_dur.items(), key=lambda kv: -kv[1])
    print(f"\n4 个 case 总时长: {grand_total/60000:.1f} 分钟\n")
    print(f"{'主题':<22} {'时长(min)':>10} {'占比':>8}")
    for topic, ms in rows:
        pct = (ms / grand_total * 100) if grand_total else 0
        print(f"{topic:<22} {ms/60000:>10.1f} {pct:>7.1f}%")

    # 出现率（命中 case 数）
    print("\n" + "=" * 80)
    print("三、主题在 case 中的命中率（出现在几个 case 里）")
    print("=" * 80)
    topic_hit = defaultdict(int)
    for cid in cases:
        for topic in topic_dur_by_case[cid]:
            topic_hit[topic] += 1
    rows = sorted(topic_hit.items(), key=lambda kv: -kv[1])
    for topic, h in rows:
        print(f"  {topic:<22} 命中 {h}/{len(cases)} 个 case")

    return cases, topic_dur_by_case, topic_lines_by_case, case_meta


if __name__ == "__main__":
    analyze()
