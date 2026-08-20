#!/usr/bin/env python3
"""Case4 完整时间线生成。注意：录音中 channel 0=teacher, channel 1=student。"""
import json
import os
import datetime as dt

BASE = "/Users/jiwenyue/Abigial/personal/work/projects/AI 销售 0 转体/真实case素材"
DIR = os.path.join(BASE, "case4_216013930")
OUT = os.path.join(BASE, "case4_完整时间线.md")


def load_call(path, start_dt, label=''):
    with open(path) as f:
        segs = json.load(f)
    out = []
    base_ts = start_dt.timestamp()
    for s in segs:
        rel_ms = int(s.get('startTime', 0))
        abs_ts = base_ts + rel_ms / 1000
        # 注意 case4 的 7.8min 通话里：channel 0=teacher (AI助教/销售), channel 1=student (孩子)
        role = '销售' if s.get('identityType') == 'teacher' else '孩子'
        text = (s.get('text', '') or '').strip()
        if not text:
            continue
        out.append({'ts': abs_ts, 'role': role, 'text': text, 'source': 'call', 'label': label})
    out.sort(key=lambda x: x['ts'])
    return out


def merge_call_lines(segs):
    if not segs:
        return []
    merged = []
    cur = dict(segs[0])
    for s in segs[1:]:
        if s['role'] == cur['role'] and s['ts'] - cur['ts'] < 3.5:
            cur['text'] = cur['text'] + ' ' + s['text']
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
        c = m.get('content', {}) or {}
        ct = c.get('contentType', '')
        ts = m.get('createdTime', 0)
        sender = str(m.get('senderRemoteId', ''))
        if sender == str(tutor_id):
            role = '销售'
        elif sender == str(user_id):
            role = '家长'
        else:
            role = '?'
        if ct == 'TEXT':
            text = c.get('content', '')
        elif ct == 'PICTURE':
            bp = c.get('bigPicture') if isinstance(c.get('bigPicture'), dict) else None
            url = bp.get('url', '') if bp else ''
            text = f'[图片] {url[:60]}...' if url else '[图片]'
        elif ct == 'SYSTEM':
            text = '[系统] ' + (c.get('content', '') or '')
            role = '系统'
        elif ct == 'VOICE':
            voice = c.get('voice', {}) if isinstance(c.get('voice'), dict) else {}
            dur = voice.get('duration', 0) if isinstance(voice, dict) else 0
            text = f'[语音 {dur}s]' if dur else '[语音]'
        else:
            text = f'[{ct}]'
        out.append({'ts': ts, 'role': role, 'text': text, 'source': 'wx', 'label': label})
    out.sort(key=lambda x: x['ts'])
    return out


events = []

# 销售期 zhangzhengxuanzz01 (3 通通话全关机 + 164 条微信)
events += load_call(os.path.join(DIR, '通话_2026-03-05_153151_0s_zzx01.json'),
                    dt.datetime(2026, 3, 5, 15, 31, 51), 'zzx01 关机 #1')
events += load_call(os.path.join(DIR, '通话_2026-03-12_205631_0s_zzx01.json'),
                    dt.datetime(2026, 3, 12, 20, 56, 31), 'zzx01 关机 #2')
events += load_call(os.path.join(DIR, '通话_2026-03-13_163047_0s_zzx01.json'),
                    dt.datetime(2026, 3, 13, 16, 30, 47), 'zzx01 关机 #3')
events += load_wechat(os.path.join(DIR, 'wechat_zhangzhengxuan01.json'),
                      '1688854382650870', '7881299499934178', label='zhangzhengxuan01（销售期）')

# 销售→助理切换瞬间 dengyaqinwh03 3 通关机
events += load_call(os.path.join(DIR, '通话_2026-03-13_191313_0s_dyq03.json'),
                    dt.datetime(2026, 3, 13, 19, 13, 13), 'dyq03 关机 #1')
events += load_call(os.path.join(DIR, '通话_2026-03-13_192838_0s_dyq03.json'),
                    dt.datetime(2026, 3, 13, 19, 28, 38), 'dyq03 关机 #2')
events += load_call(os.path.join(DIR, '通话_2026-03-13_194341_0s_dyq03.json'),
                    dt.datetime(2026, 3, 13, 19, 43, 41), 'dyq03 关机 #3')

# 助理期 dengyaqinwh03 220 条微信
events += load_wechat(os.path.join(DIR, 'wechat_dengyaqinwh03.json'),
                      '1688857640742232', '7881299499934178', label='dengyaqinwh03（助理期）')

# 助理期 7.8min 关键讲题通话
events += load_call(os.path.join(DIR, '通话_2026-03-29_首通7.8min成单关键.txt'),
                    dt.datetime(2026, 3, 29, 18, 43, 36), 'dyq03 助教讲题 7.8min')

# 4-20 短电话
events += load_call(os.path.join(DIR, '通话_2026-04-20_203038_9s_dyq03.json'),
                    dt.datetime(2026, 4, 20, 20, 30, 38), 'dyq03 9s 短电话')


# 合并通话短句 & 排序
call_segs = [e for e in events if e['source'] == 'call']
wx_segs = [e for e in events if e['source'] == 'wx']
call_merged = merge_call_lines(call_segs)
all_events = sorted(call_merged + wx_segs, key=lambda x: x['ts'])


# 输出
def write_case(events, header_md, out_path):
    lines = [header_md, '']
    cur_day = None
    cur_block = None
    for e in events:
        day = dt.datetime.fromtimestamp(e['ts']).strftime('%Y-%m-%d %A')
        if day != cur_day:
            lines.append('')
            lines.append(f'## {day}')
            lines.append('')
            cur_day = day
            cur_block = None
        block_key = (e['source'], e.get('label', ''))
        if block_key != cur_block:
            if e['source'] == 'call':
                lines.append('')
                lines.append(f'### 📞 通话 · {e.get("label","")}')
                lines.append('')
            else:
                lines.append('')
                lines.append(f'### 💬 微信 · {e.get("label","")}')
                lines.append('')
            cur_block = block_key
        ts_str = dt.datetime.fromtimestamp(e['ts']).strftime('%H:%M:%S')
        role = e['role']
        text = e['text'].replace('\n', '\n  ')
        if role == '销售':
            lines.append(f'- `{ts_str}` **销售**：{text}')
        elif role == '家长':
            lines.append(f'- `{ts_str}` 家长：{text}')
        elif role == '孩子':
            lines.append(f'- `{ts_str}` 孩子：{text}')
        elif role == '系统':
            lines.append(f'- `{ts_str}` _{text}_')
        else:
            lines.append(f'- `{ts_str}` ?: {text}')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f'wrote {out_path}: {len(events)} events')


header = """# Case 4 · 七年级·纯微信语音成单（user_id=216013930）完整时间线

> **画像**：七年级女生「可乐」，妈妈接微信，**爸爸决策**。  
> **渠道**：`zhaohui-zt-model_vip_page_show-0-0`（VIP 页 model 展示，与 case10 同源族）。  
> **销售期**：`zhangzhengxuanzz01`（正璇）—— 2026-03-12 14:23 加微 ~ 03-13 21:27 转交。  
> **助理期**：`dengyaqinwh03`（邓雅琴）—— 2026-03-13 21:28 接管至今（最后消息 5-10 13:15，跟进 ≥2 个月）。  
>
> **🔥 真实成单链路（彻底纠正之前的"方向 B 助教式"画像）**：
> | 时间 | 事件 |
> |---|---|
> | 2026-03-05 15:10 | 进班 issue 620（销售期 zzx01）|
> | 03-05 15:31 / 03-12 20:56 / 03-13 16:30 | **3 通外呼全部"您拨打的电话已关机"**（家长手机故障，3-13 20:24 家长说"我的电话打不进来 / 明天弄一下"）|
> | **03-12 14:23** | **加微成功**（销售主动加，绕过失败的电话）|
> | 03-12 14:25 | 家长 2 分钟内回「姓名可乐，七年级北师版」+ **主动追问「海豚 AI 学是怎么报课的呀？」** |
> | 03-12 14:27~14:34 | **销售/家长几乎全程微信语音对话**（销售 ≥10 条 VOICE，家长 5+ 条 VOICE）—— **相当于一通 7 分钟的"微信版首通"** |
> | 03-12 15:23 | 家长**主动追价**「咱们这个一个学期是多少钱啊」|
> | **03-13 16:54~16:58** | **完成支付 ¥1399 体验课转化**（成单关键期家长发 [OK] + [图片] 即支付截图）|
> | 03-13 21:28 | 助理期 dengyaqinwh03 接管 |
> | 03-29 18:43 | **助理期 7.8min 通话**：AI 助教带孩子做错题（绝对值/平方/相反数）—— **是成单后的服务，不是成单原因！** |
>
> **数据规模**：销售期 = 6 通通话全关机 + **164 条微信**（销售 ≥112 / 用户 = 52，互动比 **2.15 : 1**）。助理期 = 220 条微信 + 3 通有效通话（466s/9s/...）。
>
> ⚠️ **关键反差锚点（vs case9 / vs 之前的方向 B 画像）**：
>
> | 维度 | Case 4（本 case）| Case 9（成单参照）| 之前的画像 |
> |---|---|---|---|
> | 首通方式 | **微信语音对话**（电话从未接通） | 电话 6.8 min | 助教式 7.8min 讲题 |
> | 加微 → 成单 | 27 小时 | 8.5 小时 | _错_ |
> | 用户主动度 | **加微 2 分钟内主动追问报课 + 1 小时内主动追价** | 加微回小名+年级 + 主动问"怎么学习" | _错_ |
> | 通话有效率 | **0/6 通**（家长手机故障）| 1/1 通 | _错_ |
> | 决定性动作 | 销售在「电话打不通」第一时间转用微信语音 | 微信结构化追问 → 12:30 拨电话承接 | _错_ |
>
> **结论**：case4 真实路径是 **「电话失效 → 微信语音替代 → 当日/次日成单」**——这是一条**之前没被识别的成单路径 1A'**（微信版长聊/首诊），既不是 case3/9 的电话长聊（1A），也不是助教式讲题（1B）。7.8min 讲题是售后服务能力的体现，不是体验课成单动机。
"""

write_case(all_events, header, OUT)
