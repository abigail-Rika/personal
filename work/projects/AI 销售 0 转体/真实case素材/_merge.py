#!/usr/bin/env python3
"""把通话+微信整理成统一的可读 markdown 时间线"""
import json
import datetime as dt
import os

BASE = "/Users/jiwenyue/Abigial/personal/work/projects/AI 销售 0 转体/真实case素材"


def fmt_ts(ts):
    return dt.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def fmt_short(ts):
    return dt.datetime.fromtimestamp(ts).strftime('%m-%d %H:%M')


def load_call(path, start_dt):
    """加载通话文本，按 startTime 合并 teacher/student 通道，按时间排序。
    通话录音里 startTime/endTime 是从通话开始的相对毫秒。
    """
    with open(path) as f:
        segs = json.load(f)
    out = []
    base_ts = start_dt.timestamp()
    for s in segs:
        rel_ms = int(s.get('startTime', 0))
        abs_ts = base_ts + rel_ms / 1000
        role = '销售' if s.get('identityType') == 'teacher' else '家长'
        text = s.get('text', '').strip()
        if not text:
            continue
        out.append({'ts': abs_ts, 'role': role, 'text': text, 'source': 'call'})
    out.sort(key=lambda x: x['ts'])
    return out


def merge_call_lines(segs):
    """把过短的同方相邻句合并：同一发言人 2 秒内的句子合并为一段"""
    if not segs:
        return []
    merged = []
    cur = dict(segs[0])
    for s in segs[1:]:
        if s['role'] == cur['role'] and s['ts'] - cur['ts'] < 3.5:
            cur['text'] = cur['text'] + ' ' + s['text']
            cur['ts_end'] = s['ts']
        else:
            merged.append(cur)
            cur = dict(s)
    merged.append(cur)
    return merged


def load_wechat(path, tutor_id, user_id, label=''):
    with open(path) as f:
        msgs = json.load(f)
    out = []
    for m in msgs:
        c = m.get('content', {})
        ct = c.get('contentType', '')
        ts = m.get('createdTime', 0)
        sender = m.get('senderRemoteId', '')
        if sender == tutor_id:
            role = '销售'
        elif sender == user_id:
            role = '家长'
        else:
            role = '?'
        if ct == 'TEXT':
            text = c.get('content', '')
        elif ct == 'PICTURE':
            url = c.get('bigPicture', {}).get('url', '') if isinstance(c.get('bigPicture'), dict) else ''
            text = f'[图片] {url[:60]}...' if url else '[图片]'
        elif ct == 'SYSTEM':
            # 拒收 / 系统通知
            text = '[系统] ' + c.get('content', '')
            role = '系统'
        else:
            text = f'[{ct}]'
        out.append({'ts': ts, 'role': role, 'text': text, 'source': 'wx', 'label': label})
    out.sort(key=lambda x: x['ts'])
    return out


# ===== Case 1: 晨晨 1130883780 =====
case1_events = []

# 3 通通话
case1_events += load_call(os.path.join(BASE, '通话_2026-04-04_首次接通6分钟.txt'),
                          dt.datetime(2026, 4, 4, 12, 48, 11))
case1_events += load_call(os.path.join(BASE, '通话_2026-04-06_长聊45分钟.txt'),
                          dt.datetime(2026, 4, 6, 19, 31, 5))
case1_events += load_call(os.path.join(BASE, '通话_2026-05-09_召回79秒.txt'),
                          dt.datetime(2026, 5, 9, 17, 54, 47))

# 微信 conv1 (hexinwh09) + conv2 (wanglongzz02)
case1_events += load_wechat(os.path.join(BASE, 'wechat_conv1_hexinwh09.json'),
                            '1688855575659032', '7881300877011203', label='hexinwh09')
case1_events += load_wechat(os.path.join(BASE, 'wechat_conv2_wanglongzz02.json'),
                            '1688855322751290', '7881300877011203', label='wanglongzz02')

# 排序 & 合并短句
case1_events.sort(key=lambda x: x['ts'])
# call segments 合并
call_segs = [e for e in case1_events if e['source'] == 'call']
wx_segs = [e for e in case1_events if e['source'] == 'wx']
call_merged = merge_call_lines(call_segs)
all_case1 = sorted(call_merged + wx_segs, key=lambda x: x['ts'])


# ===== Case 2: 三年级 132754806 =====
case2_events = []
case2_events += load_call(os.path.join(BASE, 'case2_通话_2026-01-13_9秒短拒.txt'),
                          dt.datetime(2026, 1, 13, 18, 32, 48))
case2_events += load_call(os.path.join(BASE, 'case2_通话_2026-01-13_首通6分钟.txt'),
                          dt.datetime(2026, 1, 13, 18, 33, 41))
case2_events += load_call(os.path.join(BASE, 'case2_通话_2026-01-16_5秒短拒.txt'),
                          dt.datetime(2026, 1, 16, 19, 21, 58))

case2_events += load_wechat(os.path.join(BASE, 'case2_wechat_songsaimengzz.json'),
                            '1688855288760212', '7881299995905629', label='songsaimengzz')

case2_call = [e for e in case2_events if e['source'] == 'call']
case2_wx = [e for e in case2_events if e['source'] == 'wx']
case2_call_merged = merge_call_lines(case2_call)
all_case2 = sorted(case2_call_merged + case2_wx, key=lambda x: x['ts'])


# ===== 输出 markdown =====
def write_case(events, title, header_md, out_path):
    lines = [header_md, '']
    cur_day = None
    cur_block = None  # 'call' / 'wx'
    for e in events:
        day = dt.datetime.fromtimestamp(e['ts']).strftime('%Y-%m-%d %A')
        if day != cur_day:
            lines.append('')
            lines.append(f'## {day}')
            lines.append('')
            cur_day = day
            cur_block = None
        block = e['source']
        if block != cur_block:
            if block == 'call':
                lines.append('')
                lines.append('### 📞 通话')
                lines.append('')
            else:
                label = e.get('label', '')
                lines.append('')
                lines.append(f'### 💬 微信 · {label}')
                lines.append('')
            cur_block = block
        ts_str = dt.datetime.fromtimestamp(e['ts']).strftime('%H:%M:%S')
        role = e['role']
        text = e['text'].replace('\n', '\n  ')
        if role == '销售':
            lines.append(f'- `{ts_str}` **销售**：{text}')
        elif role == '家长':
            lines.append(f'- `{ts_str}` 家长：{text}')
        elif role == '系统':
            lines.append(f'- `{ts_str}` _{text}_')
        else:
            lines.append(f'- `{ts_str}` ?: {text}')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f'wrote {out_path}: {len(events)} events, {len(lines)} lines')


# Case 1 header
case1_header = """# Case 1 · 晨晨（user_id=1130883780）完整时间线

> **画像**：七年级（初一）女生晨晨，妈妈陈珊珊接 / 决策依赖爸爸。  
> **渠道**：抖音 19 元物理盒 - 高质量初中 (`tg-dy-1-19wulihe-gz`)。  
> **结局**：跨两期销售跟进，从未成单。  
>
> | 期 | 销售 | 进班时间 | 状态 | 备注 |
> |---|---|---|---|---|
> | issue 828 | hexinwh09（贺信） | 2026-04-04 09:15 | status=1 已释放 | 4-04~4-15 深度跟进 13 天 |
> | issue 620 | wanglongzz02（王龙） | 2026-05-09 17:15 | status=0 有效 | 召回测试 (`recallTest-1`) |
>
> **数据规模**：3 通通话（共 ~46 分钟）+ 2 个微信会话共 177 条消息。
"""

case2_header = """# Case 2 · 三年级宝贝（user_id=132754806）完整时间线

> **画像**：山东聊城三年级男生，数学英语各考 80 分（家长口径"一般"）。妈妈接电话，明显在忙，决策权交给爸爸。  
> **渠道**：APP 专题页学习计划页 9 元体验课 (`app-zt-planPage-trial_9yuan-2`) —— **典型直投落地页用户**。  
> **销售**：songsaimengzz（宋赛蒙 / 自称"赛萌老师"或"桂花老师"）。  
> **结局**：进班 status=1 已释放，13 天跟进未成单。  
>
> **数据规模**：3 通通话（仅 1 通有效 6.6 分钟，另外 2 通秒挂）+ 1 个微信会话共 76 条消息。
"""

write_case(all_case1, 'case1', case1_header,
           os.path.join(BASE, 'case1_完整时间线.md'))
write_case(all_case2, 'case2', case2_header,
           os.path.join(BASE, 'case2_完整时间线.md'))

print('done')
