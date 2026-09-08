#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
并集兜底合并：用「上一轮/更完整的基准采集」补全当前 xhs_results_full.json 中被漏采的笔记。

背景：全月重采时，部分账号因小红书懒加载 / 滚动边界问题，只采到了月末（如 7/23 之后）的
笔记，月初（如 7/1-7/22）的笔记丢失，导致账号笔记数明显偏少
（典型案例：李淑娟 7/25 采到 116 条，8/1 全月重采只 32 条，丢失 84 条）。

本脚本把基准文件中的笔记与当前数据按笔记 ID 做去重并集（只增不减），恢复漏采部分。
人工账号 (manual=True) 保持手动值，不参与并集。

用法：
  # 默认：用项目内置的 7/25 批次作为基准，补全同目录 xhs_results_full.json 的 7月数据
  python fix_leak_union.py

  # 自定义：指定基准文件、目标月范围、目标 full 文件
  python fix_leak_union.py --baseline older_results.json \
      --range 2026-07-01,2026-07-31 \
      --full xhs_results_full.json
"""
import json, shutil, os, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE = ['batch1_jul25_results.json', 'batch2_jul25_results.json']
FULL_DEFAULT = os.path.join(BASE, 'xhs_results_full.json')
JUL_FROM, JUL_TO = '2026-07-01', '2026-07-31'


def month_count(notes, frm, to):
    return sum(1 for n in notes if frm <= (n.get('d', '')[:10]) <= to)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', nargs='+', default=DEFAULT_BASELINE,
                    help='基准采集结果 JSON 文件（更完整的一轮）。可多个，空格分隔。')
    ap.add_argument('--range', default=f'{JUL_FROM},{JUL_TO}',
                    help='目标月范围，逗号分隔，如 2026-07-01,2026-07-31')
    ap.add_argument('--full', default=FULL_DEFAULT,
                    help='待修补的 xhs_results_full.json 路径')
    args = ap.parse_args()
    frm, to = [x.strip() for x in args.range.split(',')]

    full_path = args.full
    bak = full_path + '.pre_union_bak'
    if not os.path.exists(bak):
        shutil.copy2(full_path, bak)
        print(f"备份 -> {bak}")

    full = json.load(open(full_path, encoding='utf-8'))

    baseline = {}
    for f in args.baseline:
        p = f if os.path.isabs(f) else os.path.join(BASE, f)
        if os.path.exists(p):
            for e in json.load(open(p, encoding='utf-8')):
                baseline[e['xhs_id']] = e
        else:
            print(f"  ⚠️ 基准文件不存在: {p}")
    print(f"基准账号数: {len(baseline)}")

    def tot(ds):
        return sum(month_count(e.get('june_notes', []), frm, to) for e in ds if not e.get('manual')) \
               + sum(e.get('june', 0) for e in ds if e.get('manual'))

    before = tot(full)

    fixed, recovered = 0, 0
    for e in full:
        if e.get('manual'):
            continue  # 人工账号保持手动值，绝不覆盖
        xid = e['xhs_id']
        if xid not in baseline:
            continue
        merged = {n['id']: n for n in e.get('june_notes', [])}
        before_n = len(merged)
        for n in baseline[xid].get('june_notes', []):
            merged.setdefault(n['id'], n)  # 基准的笔记补进并集（只增不减）
        after_n = len(merged)
        if after_n > before_n:
            notes = sorted(merged.values(), key=lambda x: x.get('d', ''), reverse=True)
            e['june_notes'] = notes
            e['june'] = month_count(notes, frm, to)
            fixed += 1
            recovered += (after_n - before_n)

    after = tot(full)
    json.dump(full, open(full_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"修复账号数: {fixed}  补回笔记: {recovered} 条")
    print(f"并集前总额: {before}  并集后总额: {after}")


if __name__ == '__main__':
    main()
