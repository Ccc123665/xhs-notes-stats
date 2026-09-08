# -*- coding: utf-8 -*-
"""8月增量采集 driver：将 profiles.json 切片为 N 批，串行执行。
每批把子集写入 profiles.json 后调用 xhs_full_scrape.py --start 2026-08-07，
增量模式自动把新笔记(>=8/7)合并进 xhs_results_full.json（保留8/1-8/7基线）。
某批异常退出即停止，便于定位重跑。"""
import json, subprocess, sys, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get('PYTHON_EXE', sys.executable)
SCRAPE = os.path.join(BASE, "xhs_full_scrape.py")
PROFILES = os.path.join(BASE, "profiles.json")
START = "2026-08-07"
BATCHES = 4
START_BATCH = int(os.environ.get("START_BATCH", "1"))  # 从1计数的批次号，断点续跑用

profiles = json.load(open(PROFILES, encoding='utf-8'))
n = len(profiles)
size = (n + BATCHES - 1) // BATCHES
print(f"总账号 {n}，分 {BATCHES} 批，每批约 {size} 个；从批次 {START_BATCH} 开始", flush=True)

for bi in range(START_BATCH - 1, BATCHES):
    batch = profiles[bi * size:(bi + 1) * size]
    if not batch:
        continue
    json.dump(batch, open(PROFILES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n===== 批次 {bi+1}/{BATCHES}：{len(batch)} 个账号，开始 {time.strftime('%H:%M:%S')} =====", flush=True)
    t0 = time.time()
    r = subprocess.run([PY, SCRAPE, "--start", START],
                       stdout=sys.stdout, stderr=sys.stderr)
    dt = time.time() - t0
    print(f"===== 批次 {bi+1} 结束，耗时 {dt//60:.0f}分，退出码 {r.returncode} {time.strftime('%H:%M:%S')} =====", flush=True)
    if r.returncode != 0:
        print(f"!!! 批次 {bi+1} 异常退出，停止后续批次，请检查端口/夸克状态", flush=True)
        break

print("\n===== driver 执行完毕 =====", flush=True)
