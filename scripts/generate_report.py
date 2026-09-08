# -*- coding: utf-8 -*-
"""生成小红书笔记统计HTML报告"""
import json, os, sys
from datetime import date
sys.stdout.reconfigure(encoding='utf-8')

base = os.path.dirname(os.path.abspath(__file__))
results = json.load(open(os.path.join(base,'xhs_results_full.json'),'r',encoding='utf-8'))

# 自动推算统计月份（取最早和最晚笔记日期）
all_dates = []
for r in results:
    for note in r.get('june_notes', []):
        d = note.get('d','')
        if d:
            all_dates.append(d[:10])
if all_dates:
    all_dates.sort()
    d_min = all_dates[0]
    d_max = all_dates[-1]
    month_str = f"{d_min} 至 {d_max}"
else:
    month_str = "无数据"
    d_min = "2026-01-01"
    d_max = "2026-12-31"

account_count = len(results)
today_str = date.today().isoformat()

# 动态月份标签（用于表头/列名），从最早笔记日期推算
try:
    _m = int(d_min[5:7])
    month_label = f"{_m}月笔记数"
except Exception:
    month_label = "笔记数"

# 构建每个账号的按日期分布
for r in results:
    by_date = {}
    for note in r.get('june_notes', []):
        d = note.get('d','')
        by_date[d] = by_date.get(d, 0) + 1
    r['by_date'] = by_date

data_json = json.dumps(results, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小红书笔记统计报告 - {month_str}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f5;color:#333;font-size:14px}}
.header{{background:#ff2442;color:#fff;padding:20px 24px}}
.header h1{{font-size:20px;font-weight:600}}
.header p{{font-size:13px;opacity:.85;margin-top:4px}}
.controls{{background:#fff;padding:14px 24px;border-bottom:1px solid #eee;display:flex;flex-wrap:wrap;gap:12px;align-items:center;position:sticky;top:0;z-index:10;box-shadow:0 2px 6px rgba(0,0,0,.06)}}
.controls label{{font-size:13px;color:#555;white-space:nowrap}}
.controls input[type=date]{{border:1px solid #ddd;border-radius:6px;padding:5px 10px;font-size:13px;outline:none}}
.controls input[type=date]:focus{{border-color:#ff2442}}
.controls select{{border:1px solid #ddd;border-radius:6px;padding:5px 10px;font-size:13px;outline:none}}
.controls input[type=text]{{border:1px solid #ddd;border-radius:6px;padding:5px 10px;font-size:13px;outline:none;width:160px}}
.btn{{background:#ff2442;color:#fff;border:none;border-radius:6px;padding:6px 16px;cursor:pointer;font-size:13px}}
.btn:hover{{background:#e01e38}}
.btn-outline{{background:#fff;color:#ff2442;border:1px solid #ff2442;border-radius:6px;padding:6px 16px;cursor:pointer;font-size:13px}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;padding:16px 24px}}
.summary-card{{background:#fff;border-radius:10px;padding:14px 16px;text-align:center}}
.summary-card .num{{font-size:28px;font-weight:600;color:#ff2442}}
.summary-card .label{{font-size:12px;color:#888;margin-top:4px}}
.table-wrap{{padding:0 24px 24px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
th{{background:#fff5f7;color:#555;font-weight:500;padding:10px 12px;text-align:left;border-bottom:1px solid #f0f0f0;white-space:nowrap;cursor:pointer;user-select:none}}
th:hover{{background:#ffecef}}
th.sorted-asc::after{{content:" ▲";color:#ff2442;font-size:10px}}
th.sorted-desc::after{{content:" ▼";color:#ff2442;font-size:10px}}
td{{padding:9px 12px;border-bottom:1px solid #f8f8f8;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fffbfc}}
.rank{{font-size:12px;color:#aaa;font-weight:600;width:32px}}
.rank.top3{{color:#ff2442;font-weight:700}}
.count-bar{{display:flex;align-items:center;gap:8px}}
.bar{{height:8px;background:#ff2442;border-radius:4px;min-width:2px;transition:width .3s}}
.bar.zero{{background:#eee}}
.count-num{{font-weight:600;min-width:28px}}
.count-num.zero{{color:#ccc}}
.nickname a{{color:#333;text-decoration:none}}
.nickname a:hover{{color:#ff2442}}
.badge{{display:inline-block;font-size:11px;padding:1px 6px;border-radius:10px;background:#fff0f2;color:#ff2442;border:1px solid #ffd0d8;margin-left:4px;vertical-align:middle}}
.no-data{{text-align:center;padding:40px;color:#aaa;font-size:14px}}
.date-dist{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}
.date-dot{{font-size:11px;background:#fff0f2;color:#ff2442;border-radius:4px;padding:1px 5px}}
.pagination{{display:flex;justify-content:center;align-items:center;gap:8px;padding:16px}}
.page-btn{{border:1px solid #ddd;background:#fff;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:13px}}
.page-btn:hover{{border-color:#ff2442;color:#ff2442}}
.page-btn.active{{background:#ff2442;color:#fff;border-color:#ff2442}}
.page-info{{font-size:13px;color:#888}}
.export-btn{{margin-left:auto}}
@media(max-width:600px){{
  .controls{{padding:10px 12px}}
  .summary{{padding:12px}}
  .table-wrap{{padding:0 12px 20px}}
}}
</style>
</head>
<body>
<div class="header">
  <h1>小红书笔记统计报告</h1>
  <p>统计周期：{month_str} &nbsp;|&nbsp; 共 {account_count} 个账号 &nbsp;|&nbsp; 数据采集时间：{today_str}</p>
</div>

<div class="controls">
  <label>开始日期
    <input type="date" id="dateFrom" value="{d_min}">
  </label>
  <label>结束日期
    <input type="date" id="dateTo" value="{d_max}">
  </label>
  <label>搜索
    <input type="text" id="searchBox" placeholder="昵称/账号">
  </label>
  <label>筛选
    <select id="filterMode">
      <option value="all">全部账号</option>
      <option value="has">有笔记</option>
      <option value="none">无笔记</option>
    </select>
  </label>
  <button class="btn" onclick="applyFilters()">应用</button>
  <button class="btn-outline" onclick="resetFilters()">重置</button>
  <button class="btn-outline export-btn" onclick="exportCSV()">导出CSV</button>
</div>

<div class="summary" id="summaryArea"></div>

<div class="table-wrap">
<table id="mainTable">
<thead>
<tr>
  <th class="rank-col">#</th>
  <th onclick="sortBy('nickname')">昵称</th>
  <th onclick="sortBy('xhs_id')">小红书号</th>
  <th onclick="sortBy('june')" id="th-june">{month_label}</th>
  <th>日期分布</th>
</tr>
</thead>
<tbody id="tableBody"></tbody>
</table>
</div>
<div class="pagination" id="paginationArea"></div>

<script>
const RAW = {data_json};
let filtered = [];
let sortKey = 'index';
let sortDir = 1;
let page = 1;
const PAGE_SIZE = 50;

function getCount(item, from, to) {{
  const bd = item.by_date || {{}};
  if (Object.keys(bd).length === 0) {{
    // 人工核对账号：无逐日数据，按总额计入（视为落在统计周期内）
    return item.june || 0;
  }}
  let c = 0;
  for (const d in bd) {{
    if (d >= from && d <= to) c += bd[d];
  }}
  return c;
}}

function applyFilters() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  const q    = document.getElementById('searchBox').value.trim().toLowerCase();
  const mode = document.getElementById('filterMode').value;

  filtered = RAW.map((r, i) => ({{...r, _index: i, _count: getCount(r, from, to)}}))
    .filter(r => {{
      if (q && !r.nickname.toLowerCase().includes(q) && !r.xhs_id.toLowerCase().includes(q)) return false;
      if (mode === 'has' && r._count === 0) return false;
      if (mode === 'none' && r._count > 0) return false;
      return true;
    }});

  doSort();
  page = 1;
  renderSummary(from, to);
  renderTable();
  renderPagination();
}}

function resetFilters() {{
  document.getElementById('dateFrom').value = '{d_min}';
  document.getElementById('dateTo').value   = '{d_max}';
  document.getElementById('searchBox').value = '';
  document.getElementById('filterMode').value = 'all';
  applyFilters();
}}

function sortBy(key) {{
  if (sortKey === key) sortDir *= -1;
  else {{ sortKey = key; sortDir = key === 'june' ? -1 : 1; }}
  document.querySelectorAll('th').forEach(th => th.classList.remove('sorted-asc','sorted-desc'));
  const thId = 'th-' + key;
  const el = document.getElementById(thId);
  if (el) el.classList.add(sortDir === -1 ? 'sorted-desc' : 'sorted-asc');
  doSort();
  renderTable();
  renderPagination();
}}

function doSort() {{
  filtered.sort((a, b) => {{
    let av, bv;
    if (sortKey === 'june') {{ av = a._count; bv = b._count; }}
    else if (sortKey === 'index') {{ av = a._index; bv = b._index; }}
    else {{ av = a[sortKey]||''; bv = b[sortKey]||''; }}
    if (av < bv) return sortDir;
    if (av > bv) return -sortDir;
    return 0;
  }});
}}

function renderSummary(from, to) {{
  const total  = filtered.length;
  const hasN   = filtered.filter(r => r._count > 0).length;
  const sumN   = filtered.reduce((s, r) => s + r._count, 0);
  const maxN   = filtered.length ? Math.max(...filtered.map(r=>r._count)) : 0;
  document.getElementById('summaryArea').innerHTML = `
    <div class="summary-card"><div class="num">${{total}}</div><div class="label">筛选账号数</div></div>
    <div class="summary-card"><div class="num">${{hasN}}</div><div class="label">有笔记账号</div></div>
    <div class="summary-card"><div class="num">${{total-hasN}}</div><div class="label">无笔记账号</div></div>
    <div class="summary-card"><div class="num">${{sumN}}</div><div class="label">笔记总数</div></div>
    <div class="summary-card"><div class="num">${{maxN}}</div><div class="label">单账号最高</div></div>
    <div class="summary-card"><div class="num">${{hasN?Math.round(sumN/hasN):0}}</div><div class="label">有发账号均值</div></div>
  `;
}}

function renderTable() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  const maxCount = filtered.length ? Math.max(...filtered.map(r => r._count), 1) : 1;
  const start = (page-1)*PAGE_SIZE;
  const rows  = filtered.slice(start, start+PAGE_SIZE);

  if (!rows.length) {{
    document.getElementById('tableBody').innerHTML = '<tr><td colspan="5" class="no-data">暂无数据</td></tr>';
    return;
  }}

  let html = '';
  rows.forEach((r, idx) => {{
    const rank = start + idx + 1;
    const topClass = rank <= 3 ? 'top3' : '';
    const barW = r._count > 0 ? Math.round(r._count / maxCount * 120) : 0;
    const barClass = r._count === 0 ? 'zero' : '';
    const numClass = r._count === 0 ? 'zero' : '';

    // 日期分布（只显示当前筛选范围内的）
    const bd = r.by_date || {{}};
    let dateItems;
    if (Object.keys(bd).length === 0) {{
      dateItems = r.manual ? '<span class="badge">人工核对</span>' : '<span style="color:#ccc;font-size:12px">-</span>';
    }} else {{
      dateItems = Object.keys(bd)
        .filter(d => d >= from && d <= to)
        .sort()
        .map(d => `<span class="date-dot">${{d.slice(5)}}: ${{bd[d]}}</span>`)
        .join('');
      if (!dateItems) dateItems = '<span style="color:#ccc;font-size:12px">-</span>';
    }}

    html += `<tr>
      <td class="rank ${{topClass}}">${{rank}}</td>
      <td class="nickname"><a href="${{r.url}}" target="_blank">${{r.nickname}}</a></td>
      <td style="color:#888;font-size:13px">${{r.xhs_id}}</td>
      <td>
        <div class="count-bar">
          <div class="bar ${{barClass}}" style="width:${{barW}}px"></div>
          <span class="count-num ${{numClass}}">${{r._count}}</span>
        </div>
      </td>
      <td><div class="date-dist">${{dateItems}}</div></td>
    </tr>`;
  }});
  document.getElementById('tableBody').innerHTML = html;
}}

function renderPagination() {{
  const total = Math.ceil(filtered.length / PAGE_SIZE);
  if (total <= 1) {{ document.getElementById('paginationArea').innerHTML=''; return; }}
  let html = '';
  for (let i=1; i<=total; i++) {{
    html += `<button class="page-btn ${{i===page?'active':''}}" onclick="goPage(${{i}})">${{i}}</button>`;
  }}
  html += `<span class="page-info">&nbsp;共${{filtered.length}}条</span>`;
  document.getElementById('paginationArea').innerHTML = html;
}}

function goPage(p) {{ page = p; renderTable(); renderPagination(); window.scrollTo(0,0); }}

function exportCSV() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  let csv = '\\uFEFF昵称,小红书号,笔记数(' + from + '~' + to + '),主页链接\\n';
  filtered.forEach(r => {{
    csv += `"${{r.nickname}}","${{r.xhs_id}}",${{r._count}},"${{r.url}}"\\n`;
  }});
  const blob = new Blob([csv], {{type:'text/csv;charset=utf-8'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'xhs_notes_' + from + '_' + to + '.csv';
  a.click(); URL.revokeObjectURL(url);
}}

// 初始化（默认按原始顺序排列，无排序箭头）
applyFilters();
</script>
</body>
</html>"""

out = os.path.join(base, 'xhs_report.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"报告已生成: {out}")
