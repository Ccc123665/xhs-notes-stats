# 小红书笔记月度统计

从 Excel 账号花名册提取账号，通过夸克浏览器 CDP WebSocket 自动采集每个账号的笔记 ID，根据 MongoDB ObjectId 推导发布日期，统计指定月份的笔记数量，生成可筛选的交互式 HTML 报告。

## 功能

- 读取 Excel 花名册生成 `profiles.json`
- 通过 CDP (Chrome DevTools Protocol) 控制夸克浏览器自动采集
- 根据笔记 ID (ObjectId) 推导发布时间
- 增量/全量采集，支持断点续跑
- 新表 vs 旧表对比 + 旧状态回填
- 生成带筛选/排序/搜索的 HTML 报告

## 目录结构

```
.
├── SKILL.md              # WorkBuddy Skill 说明
├── README.md             # 本文件
├── .gitignore
├── references/
│   └── usage-guide.md
└── scripts/
    ├── xhs_full_scrape.py        # 核心采集脚本
    ├── generate_report.py        # 生成 HTML 报告
    ├── build_profiles_aug.py     # 从 Excel 生成 profiles.json
    ├── merge_backfill.py         # 新表对比 + 旧状态回填
    ├── update_excel_aug_full.py  # 把结果刷新回 Excel
    ├── fix_leak_union.py         # 并集兜底修复
    ├── run_aug_incremental.py    # 增量分批次 driver
    └── profiles.json             # 运行时放入自己的账号列表（示例已提供）
```

## 快速开始

1. 准备 Python 环境（推荐 3.10+），安装依赖：
   ```bash
   pip install openpyxl websocket-client requests
   ```

2. 准备账号列表：
   - 参考 `scripts/profiles.json` 填入自己的账号信息
   - 或用 `build_profiles_aug.py` 从 Excel 花名册生成

3. 启动夸克浏览器并开启远程调试端口：
   ```powershell
   & "C:\Users\你的用户名\AppData\Local\Programs\Quark\quark.exe" --remote-debugging-port=9222
   ```

4. 运行全量采集：
   ```bash
   cd scripts
   python xhs_full_scrape.py
   ```

5. 生成报告：
   ```bash
   python generate_report.py
   ```

6. （可选）并集兜底：
   ```bash
   python fix_leak_union.py
   ```

## 环境变量

- `PYTHON_EXE`：指定 Python 解释器路径（用于 `run_aug_incremental.py`、`run_aug_batches.py`）
- `XHS_EXCEL_PATH`：`merge_backfill.py` 使用的 Excel 路径
- `XHS_BATCH_BASE`：`merge_backfill.py` 使用的批次输出目录

## 注意事项

- 本仓库不包含任何真实账号、结果文件或内部 Excel。
- `profiles.json`、`xhs_results_full.json`、`xhs_report.html` 已加入 `.gitignore`。
- 请遵守小红书平台规则与当地法律法规，合理使用本工具。

## License

MIT
