# -*- coding: utf-8 -*-
"""更新 8.7_回填表: 笔记数列改为整月(8.1-8.14)数据, 状态列按整月刷新"""
import json, openpyxl, shutil
from collections import Counter

SRC = '小红书账号信息表8.7_回填.xlsx'
BAK = '小红书账号信息表8.7_回填_aug14.bak.xlsx'

# 1) 采集结果: xhs_id -> 整月8月笔记数
res = json.load(open('xhs_results_full.json', encoding='utf-8'))
june_by_xid = {r['xhs_id']: r.get('june', 0) for r in res}

# 2) 安全备份
shutil.copy(SRC, BAK)
print('已备份 ->', BAK)

# 3) 加载回填表
wb = openpyxl.load_workbook(SRC)
ws = wb.active
print('表头(更新前):', [ws.cell(1, c).value for c in range(1, ws.max_column + 1)])

# 列4 = 笔记数, 列5 = 账号状态
ws.cell(1, 4, '8月笔记数')   # 原 '8.1-8.7笔记数' -> 整月
ws.cell(1, 5, '账号状态')     # 刷新

counts = Counter()
n_fill = 0
for r in range(2, ws.max_row + 1):
    xid = str(ws.cell(r, 2).value or '').strip()
    if not xid:
        continue
    cnt = june_by_xid.get(xid, 0)
    ws.cell(r, 4, cnt)
    if cnt > 0:
        n_fill += 1
        st = '正常'
    else:
        # 不在结果中 = 从未采集的空号(温暖/谭玉芳)
        st = '0产' if xid in june_by_xid else '空'
    ws.cell(r, 5, st)
    counts[st] += 1

wb.save(SRC)
print('表头(更新后):', [ws.cell(1, c).value for c in range(1, ws.max_column + 1)])
print('状态分布:', dict(counts))
print(f'回填有笔记账号: {n_fill}  无笔记: {ws.max_row - 1 - n_fill}')
