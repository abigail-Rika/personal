"""
批量下载 20 通转写全文（OSS 公开 URL）
"""
import csv
import json
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

BASE = Path(__file__).parent
OUT_DIR = BASE / "transcripts"
OUT_DIR.mkdir(exist_ok=True)


def fetch_one(row):
    url = row["call_text_url"]
    user_id = row["user_id"]
    tutor = row["tutor_ldap"]
    dur = row["duration_s"]
    safe_name = f"u{user_id}_t{tutor}_d{dur}s"
    target = OUT_DIR / f"{safe_name}.json"
    if target.exists() and target.stat().st_size > 100:
        return user_id, "cached", str(target)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        with open(target, "wb") as f:
            f.write(content)
        try:
            data = json.loads(content)
            return user_id, f"ok ({len(content)} bytes)", str(target)
        except Exception:
            return user_id, f"ok-nojson ({len(content)} bytes)", str(target)
    except Exception as e:
        return user_id, f"err: {e}", url


def main():
    with open(BASE / "sample_20.csv") as f:
        rows = list(csv.DictReader(f))

    print(f"开始下载 {len(rows)} 通转写...")
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_one, r): r for r in rows}
        for fut in as_completed(futs):
            uid, status, path = fut.result()
            print(f"  user={uid}: {status}")
            results.append((uid, status, path))

    ok = [r for r in results if r[1].startswith("ok") or r[1] == "cached"]
    print(f"\n成功: {len(ok)}/{len(rows)}")


if __name__ == "__main__":
    main()
