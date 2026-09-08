import subprocess, shutil, os, json, time, sys

BASE = os.path.dirname(os.path.abspath(__file__))
venv = os.environ.get('PYTHON_EXE', sys.executable)
scrape = os.path.join(BASE, 'xhs_full_scrape.py')
profiles = os.path.join(BASE, 'profiles.json')
print(f"注: 本脚本为历史续跑示例，请根据实际目录修改/通过环境变量 XHS_BATCH_BASE 指定批次输出目录")

print(f"=== 8月采集 run_aug_batches 续跑启动 {time.strftime('%Y-%m-%d %H:%M:%S')} ===", flush=True)
print(f"python: {venv}", flush=True)
print(f"注: 批1已完成(48个), 本次从批2续跑", flush=True)

for i in range(2, 4):   # 续跑: 跳过已完成的批1
    b = os.path.join(base, f'profiles_batch{i}.json')
    data = json.load(open(b, encoding='utf-8'))
    shutil.copy(b, profiles)   # 当前批覆盖 profiles.json
    print(f"\n===== 批{i} 开始：{len(data)} 个账号，profiles.json 已写入 =====", flush=True)
    print(f"  批{i}首账号: {data[0]['nickname']}({data[0]['xhs_id']})", flush=True)
    t0 = time.time()
    # 每批独立子进程；脚本内部 upsert 累积到 xhs_results_full.json
    rc = subprocess.run([venv, scrape, '--start', '2026-08-01'], cwd=base)
    dt = int(time.time() - t0)
    print(f"===== 批{i} 结束 rc={rc.returncode} 耗时 {dt}s ({dt//60}分) =====", flush=True)
    # 打印当前累积账号数
    rf = os.path.join(base, 'xhs_results_full.json')
    if os.path.exists(rf):
        n = len(json.load(open(rf, encoding='utf-8')))
        print(f"  当前 xhs_results_full.json 累积账号数: {n}", flush=True)
    if rc.returncode != 0:
        print(f"⚠️ 批{i} 返回非0，但继续下批（已完成账号已 upsert 保留）", flush=True)

print(f"\n=== 全部批次完成 {time.strftime('%Y-%m-%d %H:%M:%S')} ===", flush=True)
rf = os.path.join(base, 'xhs_results_full.json')
if os.path.exists(rf):
    final = json.load(open(rf, encoding='utf-8'))
    print(f"最终账号数: {len(final)}", flush=True)
    print(f"含8月笔记的账号: {sum(1 for e in final if any('2026-08' in (n.get('d',''))[:7] for n in e.get('june_notes',[])))}", flush=True)
