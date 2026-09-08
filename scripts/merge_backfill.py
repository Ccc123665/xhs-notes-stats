# -*- coding: utf-8 -*-
"""合并 8/1采集(batch1-4) + 7/25备份恢复倒退账号 + 17人工 → xhs_results_full.json，并回填状态/笔记数列到 Excel。

关键修正：
1. 8/1 全月重采时部分账号采集失败(june==0)，用 7/25 备份(7/1-7/25)恢复其笔记。
2. 17 个人工核对值直接写入(手动优先)。
3. Excel 在 D 列回填状态(异常/0产/正常)，E 列回填 7月笔记数(含人工值)。
"""
import json, openpyxl, os

base = os.environ.get('XHS_BATCH_BASE', os.path.join(os.path.dirname(__file__), 'batch_output'))
xp = os.environ.get('XHS_EXCEL_PATH', r'请填入你的小红书账号信息表.xlsx 路径')

# 1) Excel 账号查找表 (xhs_id -> nickname/url)
wb = openpyxl.load_workbook(xp)
ws = wb.active
excel_map = {}
for r in range(2, ws.max_row + 1):
    name = str(ws.cell(r, 1).value or '').strip()
    xid = str(ws.cell(r, 2).value or '').strip()
    url = str(ws.cell(r, 3).value or '').strip()
    if not xid or xid == 'None':
        continue
    excel_map[xid] = {'nickname': name, 'xhs_id': xid, 'url': url}

# 2) 合并 8/1 四批采集结果
results = {}
for i in range(1, 5):
    d = json.load(open(f'{base}/batch{i}_results.json', encoding='utf-8'))
    for e in d:
        results[e['xhs_id']] = e
batch_count = len(results)

# 3) 从 7/25 备份恢复"倒退为0"的账号（8/1 采集失败，但 7/25 有 7/1-7/25 笔记）
jul25 = {}
for f in ['batch1_jul25_results.json', 'batch2_jul25_results.json']:
    d = json.load(open(f'{base}/{f}', encoding='utf-8'))
    for e in d:
        jul25[e['xhs_id']] = e

recovered = 0
recovered_notes = 0
for xid, e in results.items():
    if e.get('june', 0) == 0 and xid in jul25:
        j = jul25[xid]
        if len(j.get('june_notes', [])) > 0:
            # 保留 8/1 条目的昵称/url(对应新表)，用 7/25 的笔记补回
            e['june_notes'] = j['june_notes']
            e['june'] = len(j['june_notes'])
            e['total'] = j.get('total', e.get('total'))
            e['recovered_from_jul25'] = True
            recovered += 1
            recovered_notes += e['june']

# 4) 填入 17 个人工核对数据 (手动优先)
md = json.load(open(f'{base}/manual_data.json', encoding='utf-8'))
manual_added = 0
for xid, cnt in md.items():
    info = excel_map.get(xid, {'nickname': '', 'url': ''})
    results[xid] = {
        'nickname': info.get('nickname', ''),
        'xhs_id': xid,
        'url': info.get('url', ''),
        'total': cnt,
        'june': cnt,
        'june_notes': [],
        'manual': True
    }
    manual_added += 1

merged = list(results.values())
json.dump(merged, open(f'{base}/xhs_results_full.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)

# 5) 统计 + 状态判定 (异常/0产/正常)
total = sum(e.get('june', 0) for e in merged)
active = sum(1 for e in merged if e.get('june', 0) > 0)
zero = sum(1 for e in merged if e.get('june', 0) == 0)
abn = sum(1 for e in merged if e.get('abnormal'))
print(f'合并完成: 共 {len(merged)} 账号 (采集 {batch_count} + 人工 {manual_added})')
print(f'从 7/25 恢复倒退账号: {recovered} 个, 补回笔记 {recovered_notes} 条')
print(f'7月笔记总数: {total}')
print(f'正常(有发布): {active} | 0产: {zero} | 异常: {abn}')

# 6) 回填 Excel: D=状态, E=7月笔记数
status_by_xhs = {}
count_by_xhs = {}
for e in merged:
    if e.get('abnormal'):
        st = '异常'
    elif e.get('june', 0) > 0:
        st = '正常'
    else:
        st = '0产'
    status_by_xhs[e['xhs_id']] = st
    count_by_xhs[e['xhs_id']] = e.get('june', 0)

ws.cell(1, 4).value = '状态'
ws.cell(1, 5).value = '7月笔记数'
written = 0
for r in range(2, ws.max_row + 1):
    xid = str(ws.cell(r, 2).value or '').strip()
    if xid in status_by_xhs:
        ws.cell(r, 4).value = status_by_xhs[xid]
        ws.cell(r, 5).value = count_by_xhs[xid]
        written += 1

out_xp = r'E:\CC\202608\小红书账号信息表_状态.xlsx'
wb.save(out_xp)
print(f'Excel 回填: {written} 行 -> {out_xp} (D列状态, E列笔记数)')
print('异常账号列表:', [e['nickname'] + '(' + e['xhs_id'] + ')' for e in merged if e.get('abnormal')] or '无')
