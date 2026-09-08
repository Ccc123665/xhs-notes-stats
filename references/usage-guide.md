# 小红书笔记月度统计 — 使用说明

## 第一部分：本地使用（同一台电脑，后续调整账号）

### 前置条件

- 夸克浏览器（Quark）已安装并登录小红书
- Python 3.8+ 已安装 `websocket-client` 包
- 本机已生成过 `profiles.json`（账号列表）

### 常规操作流程

**场景A：账号有改动（增删账号）**

1. 修改 `profiles.json`：增删账号条目，格式参考原有条目
2. 删除 `xhs_results_full.json` 中对应 `xhs_id` 的条目（让脚本自动补采）
3. 启动夸克浏览器（双击桌面图标即可，保持前台）
4. 运行采集：
   ```bash
   python scripts/xhs_full_scrape.py
   ```
5. 采集完成后生成报告：
   ```bash
   python scripts/generate_report.py
   ```
6. 浏览器会自动打开 `xhs_report.html`

**场景B：只重新生成报告（数据不变）**

直接运行 `generate_report.py`，无需重新采集。

**场景C：完全重新采集（清空重来）**

```bash
# 删除旧结果
rm xhs_results_full.json
# 运行采集
python scripts/xhs_full_scrape.py
# 生成报告
python scripts/generate_report.py
```

**场景D：每周增量采集（推荐）**

每周跑一次，只采集最近一周的新笔记，自动与旧数据合并：
```bash
# 第1周
python scripts/xhs_full_scrape.py --start 2026-08-01
# 第2周（自动合并第1周数据）
python scripts/xhs_full_scrape.py --start 2026-08-07
# 第3周
python scripts/xhs_full_scrape.py --start 2026-08-14
# 生成报告
python scripts/generate_report.py
```
每次约 1 小时，降低反检测风险。

**场景E：按状态筛选运行（跳过空/0产账号）**

Excel 的 `status` 字段（正常/0产/空）就绪后，采集时直接用 `--status` 筛选：
```bash
# 只跑正常运营的账号
python scripts/xhs_full_scrape.py --status "正常"

# 跑正常 + 0产（跳过空账号）
python scripts/xhs_full_scrape.py --status "正常,0产"

# 组合增量 + 状态筛选
python scripts/xhs_full_scrape.py --start 2026-08-07 --status "正常"
```
> 前提：`profiles.json` 中每个账号有 `status` 字段（正常/0产/空）。Excel 该列为空则不会被匹配。

**场景F：分批执行（>80个账号）**

将 profiles.json 切片分 3-4 批，逐批跑完之后合并：
```python
# 切片示例
batch1 = all_accounts[:30]
batch2 = all_accounts[30:80]
batch3 = all_accounts[80:130]
batch4 = all_accounts[130:]
# 每批写入 scripts/profiles.json，跑完保存 batchN_results.json
# 全部跑完后合并去重
```

**场景G：回填账号状态到 Excel（D=笔记数, E=状态）**

采集完成后标注账号状态。现行列布局：**D列=笔记数，E列=账号状态**，状态词用 `正常/0产/空`：
```python
import openpyxl, json
results = json.load(open('xhs_results_full.json'))
status, count = {}, {}
for a in results:
    sid = str(a['xhs_id']).strip()
    status[sid] = '正常' if a['june'] > 0 else '0产'
    count[sid]  = a['june']

wb = openpyxl.load_workbook('账号表.xlsx')
ws = wb.active
ws.cell(1, 4).value = '8月笔记数'
ws.cell(1, 5).value = '账号状态'
for row in range(2, ws.max_row+1):
    b = str(ws.cell(row, 2).value).strip()
    if b in status:
        ws.cell(row, 4).value = count[b]
        ws.cell(row, 5).value = status[b]
wb.save('账号表_回填.xlsx')   # 建议存为新文件，不覆盖原表
```
> 更省事的入口：`update_excel_aug_full.py`（刷新整月）或 `merge_backfill.py`（新表对比回填）。

**场景H：新表对比 + 旧状态回填（"哪些账号有变动"）**

拿到新花名册、且旧表已有状态/数据时，先比对再回填，避免重复采集：
```bash
python scripts/merge_backfill.py
```
- 按「小红书号（主键）+ 主页 profile ID（兜底）」匹配
- 匹配到的账号：D列回填旧 `8月笔记数`、E列回填旧 `账号状态`
- 新表独有账号：E列标 `新增待采集`
- 输出变动清单（新增/移除/改名改链），并扫描出新表中**不可采集的 URL**（短链/creator主页/`#N/A`/`0`）
- 产物：`小红书账号信息表8.21_回填.xlsx`（原新表不变）

### 运行注意事项

- 夸克浏览器必须在采集期间保持前台、不要最小化
- 采集期间不要操作鼠标和键盘
- **脚本已内置 CDP 端口检测**：端口未开放时会自动打印启动指引，无需手动验证
- 约 130 个账号耗时 4-5 小时（含反检测等待），建议分批 40-50 个执行
- 中途断电/断网也无妨：脚本支持断点续跑，重新运行即可，已采集的不重复
- **增量采集**：每周跑一次 `python scripts/xhs_full_scrape.py --start 2026-07-08`，单次约 1 小时，自动合并旧数据

---

## 第二部分：分享给其他用户使用

### 对方需要准备什么

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows / macOS / Linux |
| Python | 3.8 以上版本 |
| 浏览器 | 任意 Chromium 内核浏览器（Chrome / Edge / 夸克 等），需已登录小红书 |
| CDP 端口 | 浏览器需以 `--remote-debugging-port=9222` 参数启动 |
| Python 包 | `pip install websocket-client` |
| Excel 文件 | 花名册含 A列=姓名、B列=小红书号、C列=含 xsec_token 的 Profile URL；已回填表追加 D列=笔记数、E列=账号状态(正常/0产/空) |

### 对方操作步骤

**第1步：安装 skill**

将 `xhs-notes-stats.zip` 发给对方，对方在 WorkBuddy 中安装此 skill 包。

**第2步：启动浏览器（CDP模式）**

Windows 示例（Chrome）：
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

macOS 示例：
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

**第3步：提供 Excel 文件**

告诉 WorkBuddy："统计这个 Excel 里的小红书账号6月笔记数"，
并附上 Excel 文件路径。WorkBuddy 会自动：

1. 读取 Excel，生成 `profiles.json`
2. 检测浏览器 CDP 端口是否就绪
3. 运行全量采集
4. 生成 HTML 报告

**第4步：等待并查看报告**

采集期间保持浏览器前台，完成后在浏览器中查看 `xhs_report.html`。

### 如果对方用夸克浏览器

夸克浏览器 Windows 安装路径通常为：
```
C:\Users\<用户名>\AppData\Local\Programs\Quark\quark.exe
```
启动命令：
```powershell
& "C:\Users\<用户名>\AppData\Local\Programs\Quark\quark.exe" --remote-debugging-port=9222
```

### 如果对方换浏览器

修改 `scripts/xhs_full_scrape.py` 第 8 行的端口号：
```python
CDP_URL = "http://localhost:XXXX"  # 改成对应端口
```

---

## 第三部分：如何保证数据准确性

### 准确性的两个核心环节

```
笔记ID提取 → 日期推导
    ↓              ↓
  DOM可见性      ObjectId公式
```

### 环节1：笔记ID提取（出错来源）

小红书页面采用懒加载，只有滚动到的区域才渲染笔记卡片。

**本 skill 采取的保障措施：**

| 措施 | 实现 | 为何有效 |
|------|------|---------|
| 新建 Tab 导航 | `Target.createTarget(url)` | 避免页面缓存导致 DOM 不完整加载 |
| 小步慢滚 | 800px/1s，最多 60 次 | 给懒加载足够的渲染时间 |
| 稳定判停 | 连续 8 次 ID 不增长才停 | 确保页面确实没有更多笔记可加载 |
| 边界早停 | 最早笔记 < 目标月首日即停止 | 避免浪费滚动时间在不需要的月份 |

### 环节2：日期推导（已验证 100% 准确）

小红书笔记 ID 是 24 位十六进制 MongoDB ObjectId：
```
前8位十六进制 → Unix 时间戳(秒) → 日期
```
- 已与多个账号的实际发布日期手动对比验证
- 内置年份校验：2018-2027 范围外视为无效

### 人工校验方法

随机抽查 2-3 个账号，打开小红书主页手动数 6 月笔记数，与报告中数据对比：

1. 在浏览器打开该账号的小红书主页
2. 手动滚动查看所有笔记，数出 6 月发布的条数
3. 在 HTML 报告搜索该账号，对比 `xhs_results_full.json` 中 `june` 值

若差异 > 2 条，说明页面渲染上限可能超出当前滚动参数，可调高 `range(60)` 和 `stable >= 8`。

### 已知局限

| 局限 | 影响 | 是否可处理 |
|------|------|-----------|
| 页面渲染数量上限 | 极高产账号（月发 >100 条）可能漏记 | 调大滚动次数可缓解，但无法完全消除 |
| 笔记被博主删除/隐藏 | 服务端已不存在 | 不可控 |
| 网络波动 | 连接偶尔断开 | 脚本自动重连，断点续跑可恢复 |
| 浏览器后台渲染暂停 | 最小化时懒加载不触发 | 保持浏览器前台即可 |
