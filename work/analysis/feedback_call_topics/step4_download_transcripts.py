"""
Step 4: 批量下载 22 通匹配电话的转写文件
"""
import csv
import json
import os
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path(__file__).parent
TR = BASE / "transcripts"
TR.mkdir(exist_ok=True)

with open(BASE / "matched_calls.csv") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"待下载: {len(rows)} 通")


def safe_filename(call_id: str) -> str:
    return call_id.replace(":", "_").replace("/", "_")


def download(row):
    cid = row["call_id"]
    url = row["url"]
    fname = TR / f"{safe_filename(cid)}.json"
    if fname.exists() and fname.stat().st_size > 100:
        return ("skip", cid, fname.stat().st_size)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(fname, "wb") as f:
            f.write(data)
        return ("ok", cid, len(data))
    except Exception as e:
        return ("err", cid, str(e))


with ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(download, r) for r in rows]
    for fut in as_completed(futures):
        status, cid, info = fut.result()
        print(f"  [{status}] {cid[:30]:<32} {info}")

# 校验
total = 0
errs = 0
for r in rows:
    fname = TR / f"{safe_filename(r['call_id'])}.json"
    if fname.exists() and fname.stat().st_size > 100:
        total += 1
    else:
        errs += 1
        print(f"FAIL: {r['call_id']}")
print(f"\n成功下载: {total} / {len(rows)}, 失败: {errs}")
