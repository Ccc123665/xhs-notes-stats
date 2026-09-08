import openpyxl, json, urllib.request
from collections import OrderedDict, Counter

# ---- 读取8.7回填表(最新账号花名册) ----
wb = openpyxl.load_workbook('小红书账号信息表8.7_回填.xlsx'); ws = wb.active
rows = []
for r in range(2, ws.max_row + 1):
    name = str(ws.cell(r, 1).value or '').strip()
    xid = str(ws.cell(r, 2).value or '').strip()
    url = ws.cell(r, 3).value
    if not xid:
        continue
    rows.append({'name': name, 'xid': xid, 'url': str(url or '')})

# ---- 读取现有结果(含已展开的标准链接) ----
res = json.load(open('xhs_results_full.json', encoding='utf-8'))
res_url = {r['xhs_id']: r.get('url', '') for r in res}

def is_std(u):
    return 'xiaohongshu.com/user/profile/' in str(u)

def is_short(u):
    return 'xhslink.com' in str(u)

groups = OrderedDict()
for row in rows:
    groups.setdefault(row['xid'], []).append(row)

profiles = []
short_links = []
skipped = []
for xid, grp in groups.items():
    # 优先用结果文件里已展开的标准链接
    if res_url.get(xid) and is_std(res_url[xid]):
        profiles.append({'nickname': grp[0]['name'], 'xhs_id': xid, 'url': res_url[xid]})
        continue
    std = [g for g in grp if is_std(g['url'])]
    if std:
        profiles.append({'nickname': std[0]['name'], 'xhs_id': xid, 'url': std[0]['url']})
        continue
    short = [g for g in grp if is_short(g['url'])]
    if short:
        short_links.append((xid, grp[0]['name'], short[0]['url']))
        continue
    skipped.append((xid, grp[0]['name']))

# 展开短链
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
for xid, name, link in short_links:
    try:
        req = urllib.request.Request(link, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            final = resp.geturl()
        if is_std(final):
            profiles.append({'nickname': name, 'xhs_id': xid, 'url': final})
        else:
            skipped.append((xid, name + '(展开后非标准链)'))
    except Exception as e:
        skipped.append((xid, name + '(短链展开失败)'))

json.dump(profiles, open('profiles.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('8.7 数据行:', len(rows), '| 唯一小红书号:', len(groups))
print('本次待采集账号(profiles.json):', len(profiles))
print('跳过(无有效链接):', len(skipped))
for s in skipped:
    print('   ⚠️', s)
print()
# 基线核对
alld = []
for r in res:
    for n in r.get('june_notes', []):
        alld.append(n.get('d', '')[:10])
c = Counter(alld)
print('基线账号数:', len(res), '| 基线8月笔记数:', len(alld))
print('基线日期范围:', min(alld), '->', max(alld))
