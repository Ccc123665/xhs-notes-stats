---
name: xhs-notes-stats
description: 小红书笔记月度统计。从 Excel 账号花名册提取账号，通过夸克浏览器 CDP WebSocket 自动采集每个账号的笔记ID，根据 MongoDB ObjectId 推导发布日期，统计指定月份的笔记数量，生成可筛选的交互式 HTML 报告。支持按账号状态（正常/0产/空）筛选、分批执行、结果回填Excel、以及「新表 vs 旧表对比 + 旧状态回填」。触发词：小红书笔记统计、小红书月度笔记、xhs notes stats、账号对比回填。
agent_created: true
---

# 小红书笔记月度统计

> 最后更新：2026-08-21（同步 8 月工作流：D=笔记数 / E=状态 列布局、正常/0产/空 词表、新表对比回填流程、刷新核心脚本）。

## 目的

从 Excel 中提取小红书账号列表，通过 CDP 浏览器自动化采集每个账号的笔记数据，
根据 MongoDB ObjectId 推导发布日期，统计指定月份的笔记数，输出交互式 HTML 报告。

## 触发条件

当用户提到以下关键词时使用此 skill：
- "统计小红书笔记" / "小红书笔记统计" / "xhs notes stats"
- 提供小红书账号 Excel 并要求统计笔记数
- 附加起始日期如 "起始日期 2026-08-07" "从8月7日开始统计"
- **"对比上次的表 / 把旧状态回填到新表 / 哪些账号有变动"** → 走「新表对比 + 旧状态回填」流程

## 核心链路

```
Excel花名册 → profiles.json → CDP WebSocket (夸克浏览器:9222) →
逐账号新建Tab → 小步慢滚提取笔记ID → ObjectId推导日期 →
xhs_results_full.json → generate_report.py → xhs_report.html
                                    ↑
               update_excel_aug_full.py / merge_backfill.py 回填 Excel
```

## 必需文件

| 文件 | 说明 |
|------|------|
| `scripts/xhs_full_scrape.py` | 全量/增量采集脚本（断点续跑 + CDP自动重连 + 状态筛选） |
| `scripts/generate_report.py` | 生成交互式HTML报告 |
| `scripts/fix_leak_union.py` | 并集兜底修复：用更完整的基准采集补全漏采笔记（防全月重采漏采） |
| `scripts/build_profiles_aug.py` | 8月专用：从回填花名册生成 profiles.json（自动展开短链、优先用结果里的标准链接） |
| `scripts/run_aug_incremental.py` | 8月专用：把 profiles.json 切片成 N 批串行增量采集的 driver |
| `scripts/run_aug_batches.py` | 8月专用：分批次续跑示例（含硬编码路径，需按需改） |
| `scripts/merge_backfill.py` | **新表对比 + 旧状态回填**：把旧表的状态/数据回填进新花名册，并报告变动 |
| `scripts/update_excel_aug_full.py` | 把 xhs_results_full.json 的整月笔记数/状态刷新回 8月回填表 |

### Excel 数据源格式（2026-08 现行）

**新花名册（如 `小红书账号信息表8.21.xlsx`）**：
- **A列**：姓名/昵称
- **B列**：小红书号（数字ID 或 字母手柄，如 `v_offcn992`）
- **C列**：主页链接（含 xsec_token 的完整 Profile URL，或短链/异常值）

**已回填表（如 `小红书账号信息表8.7_回填.xlsx`）** 在此基础上追加：
- **D列**：`8月笔记数`（采集后回填）
- **E列**：`账号状态`，取值 **`正常` / `0产` / `空`**（另有瞬态值 `异常`/`未采集`/`新增待采集`）

> ⚠️ 7月时代的旧文档曾把状态写在 **D列**、用词 `7月正常运营/7月零产/空账号` —— 现已统一为
> **D=笔记数、E=状态**，词表 **正常/0产/空**。凡是看到 D列=状态 的旧说明都按此更正。

## 执行流程

### 第1步：准备 profiles.json

从用户提供的 Excel 花名册读取账号，**读取 A(姓名)、B(小红书号)、C(主页链接)**，生成 `profiles.json`：

```json
[
  {
    "nickname": "昵称",
    "xhs_id": "小红书号",
    "url": "https://www.xiaohongshu.com/user/profile/xxxxx?xsec_token=xxx",
    "status": "正常"
  }
]
```

要求：
- 只保留 C 列有有效 Profile URL 的账号（短链 `xhslink.com/m/...` 需先展开为标准形式）
- xsec_token 必须保留在 URL 中（否则访问会被拦截）
- 若花名册已有状态列（E列），一并读入 `status` 字段，供 `--status` 筛选

**8月快捷方式**：直接用 `build_profiles_aug.py` —— 它读取回填花名册 + `xhs_results_full.json`，
自动优先采用结果文件里已展开的标准链接、并展开短链，输出干净的 `profiles.json`：
```bash
python scripts/build_profiles_aug.py
```

### 第2步：确认浏览器环境

脚本已内置 CDP 端口自动检测（默认 `http://localhost:9222`，见 `xhs_full_scrape.py` 顶部 `CDP_URL`）。
端口未开放时自动打印指引并退出。提前确认：
```bash
curl -s http://localhost:9222/json/version | head -c 200
```
无响应则启动夸克：
```powershell
& "C:\Users\Administrator\AppData\Local\Programs\Quark\quark.exe" --remote-debugging-port=9222
```

### 第3步：运行采集

两种模式 + 状态筛选：

**全量模式**（首次或完全重采）：
```bash
python scripts/xhs_full_scrape.py
```

**增量模式**（每周追加，自动合并旧结果）：
```bash
python scripts/xhs_full_scrape.py --start 2026-08-07
```

**按状态筛选**（只跑指定状态，跳过空/0产）：
```bash
python scripts/xhs_full_scrape.py --status "正常"
python scripts/xhs_full_scrape.py --status "正常,0产"
python scripts/xhs_full_scrape.py --start 2026-08-07 --status "正常"
```
> `--status` 读取 `profiles.json` 中每个账号的 `status` 字段（正常/0产/空），不符合的在采集前剔除。

增量模式特点：
- 重新采集所有账号，遇到早于 `--start` 的笔记立即停止滚动
- 自动将本期新增笔记与 `xhs_results_full.json` 旧数据按 xhs_id upsert 合并（**不丢其他账号**）
- 无新笔记的账号极快跳过

脚本特性：断点续跑 / CDP 自动重连(3级Origin回退) / 新建Tab导航 / 小步慢滚(400-1200px,stable≥8) /
6月(月)边界早停 / 异常重试 / 反检测(stealth指纹+随机滚动+账号间等待)。

运行期间保持夸克前台、不最小化、不操作键鼠。130 账号约 4-5 小时，建议分批 40-50 个。

### 第3.5步：并集兜底（强烈推荐，防全月重采漏采）

只要做了全量/重采（不加 `--start`），就跑一次：
```bash
python scripts/fix_leak_union.py
```
只增不减地补回缺失笔记，自动跳过人工核对账号（`manual=True`）。

### 第4步：生成 HTML 报告

```bash
python scripts/generate_report.py
```
输出 `xhs_report.html`：日期范围筛选 / 搜索 / 有无笔记筛选 / 表头排序 / 导出CSV /
标题·日期·账号数·采集时间均从数据自动推算。

### 第3.x步：新表对比 + 旧状态回填（2026-08 新增）

当拿到一份**新花名册**，且手头有一份**上次已回填状态/数据的旧表**时，先比对变动、再把旧状态回填进新表，
避免重复采集已统计账号、并标出需新采集的账号。

```bash
python scripts/merge_backfill.py
```
（脚本内 `NEW` / `OLD` / `OUT` 三个路径按当次文件改；默认 NEW=8.21、OLD=8.7_回填、OUT=8.21_回填）

逻辑：
1. **匹配键**：小红书号（主键） + 主页 profile ID（兜底，应对「同号不同链接/改名」）。
2. **回填**：新表中与旧表匹配的账号，D列填旧 `8月笔记数`、E列填旧 `账号状态`；
   新表独有账号 → E列标 `新增待采集`、D列留空。
3. **变动报告**：输出 匹配数 / 新增 / 移除 / 信息变动（改名·链接变更）清单。
4. **数据质量扫描**：标出新表中**无法采集**的 URL（短链 `xhslink`、creator 主页、`#N/A`、字面 `0` 等），
   其中「旧表有完整URL」的会提示可一键恢复。

产物：`小红书账号信息表8.21_回填.xlsx`（原新表不变）。后续仅对 `新增待采集` 账号跑采集即可。

### 第4.x步：把采集结果刷新回 Excel

采集完成后，把整月笔记数/状态写回 8月回填表：
```bash
python scripts/update_excel_aug_full.py
```
（先备份原表，再把 D列=8月笔记数、E列=账号状态 按 xhs_id 刷新；cnt>0→正常，否则 0产/空。）

## 高级用法

### 按账号状态筛选运行

| 指令 | 命令 | 效果 |
|------|------|------|
| "只跑正常运营" | `--status "正常"` | 跳过 0产/空，直奔有产出的 |
| "跑正常和0产" | `--status "正常,0产"` | 剔除空账号，检查恢复情况 |
| "全部跑" | 不加 `--status` | 所有账号都跑 |

> 前提：`profiles.json` 中每个账号有 `status` 字段（正常/0产/空）。Excel 该列为空则不会被匹配。

### 分批执行（大批量推荐）

账号 > 80 时建议分 3-4 批，降低反检测风险。推荐用 `run_aug_incremental.py`（自动按 `BASE` 目录切片、串行调用）：
```bash
python scripts/run_aug_incremental.py            # 默认4批, --start 2026-08-07
START_BATCH=2 python scripts/run_aug_incremental.py   # 断点续跑, 从第2批开始
```
或直接手搓切片（见旧 `run_aug_batches.py` 示例，注意其中的硬编码路径需改成你的项目目录）：
```
1. profiles.json 切片为 batch1(前30)/batch2(中50)/batch3(中50)/batch4(剩余)
2. 每批写入 scripts/profiles.json 后跑 xhs_full_scrape.py（增量模式勿清空 full 文件）
3. 逐批跑完即完整（增量 upsert 合并）；全量模式则需 Python 合并去重
4. （全量）合并后跑 fix_leak_union.py 并集兜底
5. generate_report.py 生成报告
```
单批耗时：30个~1h，50个~1.5-2h，60个~2-3h。

### 回填账号状态到 Excel

分类逻辑（cnt = 统计月笔记数）：
```
cnt > 0              → "正常"
cnt == 0 且曾采集     → "0产"        # 历史有，本月停
从未出现在结果中      → "空"         # 空账号/未采集
```
用 openpyxl 按 B列(小红书号) 匹配，D列写笔记数、E列写状态。未匹配标记"未找到"。
`merge_backfill.py` / `update_excel_aug_full.py` / `add_status_col.py` 均为该逻辑的不同入口。

## 关键技术要点

### 笔记ID提取
```javascript
document.querySelectorAll('a[href*="/explore/"]')
```
从 href 中正则提取 24 位十六进制笔记 ID。

### 日期推导（100% 准确）
笔记 ID 前 8 位十六进制 → Unix 时间戳(秒) → 日期。年份不在 2018-2027 范围内视为无效。
```python
ts = int(note_id[:8], 16)
date = datetime.fromtimestamp(ts, tz=timezone.utc)
```

### CDP 连接恢复
3 级 Origin 回退：`devtools://devtools` → `null` → `suppress_origin`。

## ⚠️ 致命坑点

### 坑点1：直接改 URL 导航导致漏数据
**永远不要**在已有 tab 上 `window.location.href = newUrl` 切换账号——缓存/状态不会完全刷新，部分笔记不渲染。
**正确做法**：每个账号 `Target.createTarget(url)` 新建独立 tab，完毕 `Target.closeTarget(tid)` 关闭。

### 坑点2：大步快跳滚动导致漏数据
3000px 大步快跳下懒加载来不及渲染就已"路过"。
**正确做法**：800px 小步慢滚（1秒间隔），稳定判停阈值 `stable >= 8` 连续不增长。

### 坑点3：增量模式（`--start`）覆盖全量结果文件（旧版 bug，本版已修复）
旧版增量模式 `results = []` 后只 `append` 本次 `profiles.json` 里的账号，写 `xhs_results_full.json` 时**只保留子集，丢掉其他账号（含人工值、历史数据）**。
**正确做法（本版）**：增量模式让 `results` 初始持有 `xhs_results_full.json` 全部旧账号，本次用 `_upsert` 按 xhs_id 替换，其余原样保留。

> ⚠️ 任何增量补采前，务必先备份 `xhs_results_full.json`，确认脚本用 upsert 而非纯 append。

### 坑点4：全月重采漏采（部分账号只采到月末子集）
全量重采时个别账号只采到月末几天，月初大量笔记丢失，天数集中在月末，且不报错极难发现。
**正确做法 —— 并集兜底**：用「更完整的基准采集」与当前结果做 ID 去重并集（只增不减）：
```bash
python scripts/fix_leak_union.py
# 自定义基准/范围/目标：
python scripts/fix_leak_union.py --baseline older_full_results.json --range 2026-08-01,2026-08-31 --full xhs_results_full.json
```
人工账号（`manual=True`）自动跳过，绝不被覆盖。跑完重跑 `generate_report.py` 和 Excel 回填。

### 坑点5：跨月越界笔记污染统计月
全月重采时少数账号会抓到统计月之外的笔记（如统计8月却抓到9/1），被算进当月 `june` 字段，报告默认范围被推断到9/1。
**正确做法**：合并/生成前用统计月范围 `[首月1日, 月末日]` 过滤 `june_notes` 并重算 `june`。
`fix_leak_union.py` 的 `month_count` 已按 `--range` 严格计数；如需彻底清除越界条目，合并阶段加：
`notes = [n for n in notes if FR <= (n.get('d','')[:10]) <= TO]`。

## 后续调整

1. **浏览器换了**：改 `xhs_full_scrape.py` 顶部 `CDP_URL` 端口号（默认 9222）
2. **账号有增减**：改 `profiles.json`，删 `xhs_results_full.json` 中对应条目即自动补采
3. **增量采集**：`--start YYYY-MM-DD`，每周跑一次自动合并
4. **滚动参数调整**：改 `range(50)` 与 `stable >= 8`
5. **重新生成报告**：直接跑 `generate_report.py`
6. **新表对比回填**：跑 `merge_backfill.py`（改脚本内 NEW/OLD/OUT 路径）
7. **刷新 Excel 状态**：跑 `update_excel_aug_full.py`
