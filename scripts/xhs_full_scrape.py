# -*- coding: utf-8 -*-
"""小红书笔记全量采集 - 支持断点续跑、增量采集
用法:
  python xhs_full_scrape.py                                      # 全量采集（默认2026-06-01起）
  python xhs_full_scrape.py --start 2026-07-08                   # 增量采集（指定起始日期）
  python xhs_full_scrape.py --status "7月正常运营"                # 只跑D列为"7月正常运营"的账号
  python xhs_full_scrape.py --status "7月零产,7月正常运营"         # 跑多个状态（逗号分隔）
  python xhs_full_scrape.py --start 2026-07-08 --status "7月正常运营"  # 组合使用"""
import json, urllib.request, sys, os, time, websocket, random, re
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')
TZ = timezone(timedelta(hours=8))
CDP_URL = "http://localhost:9222"

base = os.path.dirname(os.path.abspath(__file__))
PROFILES_FILE = os.path.join(base, 'profiles.json')
RESULTS_FILE  = os.path.join(base, 'xhs_results_full.json')
PROGRESS_FILE = os.path.join(base, 'xhs_progress.json')

def http_get(path):
    with urllib.request.urlopen(f"{CDP_URL}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode('utf-8'))

def find_xhs_pages():
    pages = http_get("/json/list")
    return [p for p in pages if p.get('type')=='page'
            and 'www.xiaohongshu.com' in p.get('url','')
            and 'devtools' not in p.get('url','')]

def id_to_date(nid):
    if not nid or len(nid)<8: return None
    try:
        ts = int(nid[:8], 16)
        d = datetime.fromtimestamp(ts, tz=TZ)
        if d.year < 2018 or d.year > 2027: return None
        return d.strftime('%Y-%m-%d')
    except:
        return None

EXTRACT = r"""(function(){
  var ids=[];
  document.querySelectorAll('a[href*="/explore/"]').forEach(function(a){
    var h=a.href||a.getAttribute('href')||'';
    var m=h.match(/\/explore\/([a-f0-9]{24})/);
    if(m) ids.push(m[1]);
  });
  var u=[], s={};
  ids.forEach(function(id){if(!s[id]){s[id]=1;u.push(id)}});
  return u;
})()"""

# 反检测：隐藏自动化指纹
STEALTH_JS = """(function(){
  Object.defineProperty(navigator, 'webdriver', {get: function(){return undefined}});
  var cdcVars = [];
  for (var key in window) { if (key.startsWith('cdc_')) cdcVars.push(key); }
  cdcVars.forEach(function(k){ delete window[k]; });
  try { delete window.__playwright__binding__; } catch(e) {}
})()"""

class CDP:
    def __init__(self):
        info = http_get("/json/version")
        ws_url = info['webSocketDebuggerUrl']
        # 3级Origin回退
        try:
            self.ws = websocket.create_connection(ws_url, timeout=10, origin="devtools://devtools")
            print("CDP连接: devtools://devtools")
        except Exception:
            try:
                self.ws = websocket.create_connection(ws_url, timeout=10, origin="null")
                print("CDP连接: null origin")
            except Exception:
                self.ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
                print("CDP连接: suppress_origin")
        self.mid = 0

    def _reconnect(self):
        """重建WebSocket连接"""
        try: self.ws.close()
        except: pass
        time.sleep(2)
        info = http_get("/json/version")
        ws_url = info['webSocketDebuggerUrl']
        try:
            self.ws = websocket.create_connection(ws_url, timeout=10, origin="devtools://devtools")
        except Exception:
            try:
                self.ws = websocket.create_connection(ws_url, timeout=10, origin="null")
            except Exception:
                self.ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        print("  [CDP重连成功]", flush=True)

    def _send(self, method, params=None, sid=None, timeout=30):
        self.mid += 1
        msg = {"id": self.mid, "method": method}
        if params: msg["params"] = params
        if sid: msg["sessionId"] = sid
        try:
            self.ws.send(json.dumps(msg))
        except Exception:
            # 连接断开，重建
            self._reconnect()
            self.mid += 1
            msg["id"] = self.mid
            self.ws.send(json.dumps(msg))
        start = time.time()
        while time.time()-start < timeout:
            self.ws.settimeout(max(1, timeout - (time.time()-start) + 1))
            try:
                r = json.loads(self.ws.recv())
                if r.get('id') == self.mid: return r
            except websocket.WebSocketTimeoutException:
                return {"error": "timeout"}
            except Exception as e:
                return {"error": str(e)}
        return {"error": "timeout"}

    def create_tab(self, url):
        """用Target.createTarget新建tab，避免页面缓存问题"""
        r = self._send("Target.createTarget", {"url": url})
        return r.get('result', {}).get('targetId')

    def close_target(self, tid):
        try: self._send("Target.closeTarget", {"targetId": tid})
        except: pass

    def attach(self, tid):
        r = self._send("Target.attachToTarget", {"targetId": tid, "flatten": True})
        sid = r.get('result', {}).get('sessionId')
        # 注入反检测脚本（隐藏 webdriver 等自动化指纹）
        if sid:
            try: self.eval(STEALTH_JS, sid, timeout=5)
            except: pass
        return sid

    def eval(self, expr, sid, timeout=30):
        r = self._send("Runtime.evaluate",
                       {"expression": expr, "returnByValue": True, "awaitPromise": False},
                       sid, timeout)
        if 'error' in r: return {"error": r['error']}
        res = r.get('result', {}).get('result', {})
        if res.get('type') == 'undefined' or res.get('subtype') == 'null': return None
        return res.get('value')

    def close(self):
        try: self.ws.close()
        except: pass

# ========== CDP 端口检测与启动指引 ==========
def check_cdp_port():
    """检测 CDP 端口是否已开放。已开放则静默通过，未开放则打印3步指引后退出。"""
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return  # 端口已通，无需指引
    except Exception:
        pass
    
    # 检测系统可用浏览器
    browsers = _find_browsers()
    
    print("=" * 56)
    print("  CDP 调试端口未开放")
    print("=" * 56)
    print()
    print("  请按以下 3 步操作：")
    print()
    print("  第1步：彻底关闭浏览器")
    print("    Ctrl+Shift+Esc → 进程 → 搜索并结束所有浏览器进程")
    print("    (chrome / edge / quark，一个都别留)")
    print()
    print("  第2步：用命令行带参数启动浏览器")
    print("    Win+R → 输入 cmd → 回车，粘贴以下命令：")
    print()
    
    for name, path in browsers:
        quoted = f'"{path}"' if ' ' in path else path
        print(f"    [{name}]")
        print(f'    {quoted} --remote-debugging-port=9222')
        print()
    
    if not browsers:
        print("    (未检测到夸克/Chrome/Edge，请手动启动任意Chromium浏览器")
        print("     并加上参数: --remote-debugging-port=9222)")
        print()
    
    print("  第3步：验证端口通了")
    print("    curl http://localhost:9222/json/version")
    print("    或用浏览器打开 http://localhost:9222/json/version")
    print("    看到 JSON 数据 = 成功")
    print()
    print("  验证通过后，重新运行本脚本即可。")
    print("=" * 56)
    sys.exit(1)


def _find_browsers():
    """搜索系统已安装的浏览器（夸克→Chrome→Edge 优先级），返回 [(名称, 路径)]。"""
    found = []
    localappdata = os.environ.get('LOCALAPPDATA', '')
    program_files = os.environ.get('ProgramFiles', '')
    program_files_x86 = os.environ.get('ProgramFiles(x86)', '')
    
    # 夸克
    quark_paths = [
        os.path.join(localappdata, 'Programs', 'Quark', 'quark.exe'),
        r'D:\Program Files\Quark\quark.exe',
    ]
    for p in quark_paths:
        if os.path.exists(p):
            found.append(('夸克', p))
            break
    
    # Chrome
    chrome_paths = [
        os.path.join(program_files, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(program_files_x86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(localappdata, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            found.append(('Chrome', p))
            break
    
    # Edge
    edge_paths = [
        os.path.join(program_files_x86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(program_files, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ]
    for p in edge_paths:
        if os.path.exists(p):
            found.append(('Edge', p))
            break
    
    return found

# ========== 解析参数 ==========
start_date = '2026-06-01'  # 默认起始日期
is_incremental = False
status_filter = None  # D列账号状态筛选（逗号分隔的列表，如 "7月正常运营,7月零产"）
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == '--start' and i + 1 < len(args):
        start_date = args[i + 1]
        is_incremental = (start_date != '2026-06-01')
    elif arg == '--status' and i + 1 < len(args):
        status_filter = [s.strip() for s in args[i + 1].split(',')]

month_label = f"{int(start_date[5:7])}月"
print(f"统计起始日期: {start_date}")
if status_filter:
    print(f"账号状态筛选: {', '.join(status_filter)}")
if is_incremental:
    print("【增量模式】将合并已有数据\n")

# ========== 加载数据 ==========
with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
    all_profiles = json.load(f)

# D列状态预筛选（如 Excel D 列有"空账号/7月零产/7月正常运营"）
if status_filter:
    before = len(all_profiles)
    all_profiles = [p for p in all_profiles if p.get('status', '') in status_filter]
    skipped = before - len(all_profiles)
    print(f"状态筛选: {before} → {len(all_profiles)} 个（跳过 {skipped} 个不符合的账号）\n")

# 加载已有结果（断点续跑 / 增量合并）
old_results = []
old_notes_map = {}  # xhs_id → {note_id: note_dict}，增量模式用
if os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        old_results = json.load(f)
    if is_incremental:
        for r in old_results:
            old_notes_map[r['xhs_id']] = {n['id']: n for n in r.get('june_notes', [])}
        print(f"已有数据: {len(old_results)} 个账号（将合并）")
    else:
        done_ids = {r['xhs_id'] for r in old_results if r.get('total', 0) > 0 or r.get('june', 0) > 0}
        print(f"断点续跑: 已完成 {len(done_ids)} 个账号")

def _upsert(results, entry):
    """按 xhs_id 替换已有条目，不存在则追加。增量模式防止覆盖其他账号数据。"""
    for idx, r in enumerate(results):
        if r.get('xhs_id') == entry.get('xhs_id'):
            results[idx] = entry
            return
    results.append(entry)


def safe_save(results):
    """原子保存结果文件，规避文件监视/同步的间歇锁定。
    失败仅警告、绝不抛异常（数据仍在内存，下次重跑同一账号会幂等补齐）。"""
    _tmp = RESULTS_FILE + '.tmp'
    _last = None
    for _att in range(20):
        try:
            with open(_tmp, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=1)
            os.replace(_tmp, RESULTS_FILE)
            return True
        except (PermissionError, OSError) as e:
            _last = e
            time.sleep(min(0.5 * (_att + 1), 5))
    print(f"  ⚠️ 保存失败(已重试20次): {_last}")
    return False


if is_incremental:
    # 增量模式：重新采集所有账号（快速跳过无新笔记的）
    # 关键修复：results 初始持有全部旧账号，本次采集按 xhs_id upsert 替换，
    #           防止只写本次子集而覆盖丢弃其他账号（含人工/历史数据）。
    #           （旧版 results=[] 会导致最终文件只剩本次 profiles 子集，丢数据。）
    profiles = all_profiles
    results = list(old_results)   # 含全部旧账号；首次增量 old_results=[] 则为空
    total_all = len(all_profiles)
    done_ids = set()
else:
    done_ids = {r['xhs_id'] for r in old_results} if old_results else set()
    profiles = [p for p in all_profiles if p.get('xhs_id') not in done_ids]
    results = old_results if old_results else []
    total_all = len(all_profiles)

print(f"待采集: {len(profiles)} 个 / 共 {total_all} 个\n")

# ========== 采集 ==========
check_cdp_port()
cdp = CDP()
print("CDP已连接\n")

for i, p in enumerate(profiles):
    nick, url = p['nickname'], p['url']
    xhs_id = p.get('xhs_id', '')
    done_count = len(done_ids) + i + 1
    if is_incremental:
        done_count = i + 1
    print(f"[{done_count}/{total_all}] {nick} ({xhs_id})", flush=True)

    # 用 createTarget 新建tab（避免页面缓存导致漏数据）
    tid = cdp.create_tab(url)
    if not tid:
        print("  创建tab失败，跳过", flush=True)
        fail_entry = {"nickname": nick, "xhs_id": xhs_id, "url": url,
                      "total": 0, "june": 0, "june_notes": [], "error": "create_tab_fail", "abnormal": True}
        # 增量模式：保留旧数据
        if is_incremental and xhs_id in old_notes_map:
            old_notes = sorted(old_notes_map[xhs_id].values(), key=lambda x: x['d'], reverse=True)
            fail_entry["june_notes"] = old_notes
            fail_entry["june"] = len(old_notes)
            fail_entry["total"] = len(profiles)  # 保留上次数
            fail_entry["error"] = "create_tab_fail_kept_old"
        _upsert(results, fail_entry)
        done_ids.add(xhs_id)
        safe_save(results)
        continue

    time.sleep(5)
    sid = cdp.attach(tid)
    time.sleep(3)

    title = cdp.eval('document.title', sid) or ''
    print(f"  标题: {title}", flush=True)

    # 异常页面重试
    if '发现' in title or title == '':
        print("  异常页面，重建tab...", flush=True)
        cdp.close_target(tid)
        tid = cdp.create_tab(url)
        if tid:
            time.sleep(5)
            sid = cdp.attach(tid)
            time.sleep(3)
            title = cdp.eval('document.title', sid) or ''
            print(f"  重试标题: {title}", flush=True)

    # 异常账号检测（用户不存在/已注销/账号异常等）
    abnormal = False
    try:
        body_text = cdp.eval('(document.body&&document.body.innerText||document.documentElement.innerText||"").slice(0,400)', sid, timeout=5) or ''
        body_text = str(body_text)
        if any(k in body_text for k in ['用户不存在','账号不存在','该用户','已注销','账号已注销','页面不存在','访问受限','内容不存在','账号异常']):
            abnormal = True
            print("  ⚠️ 检测到异常账号页面", flush=True)
    except Exception:
        pass

    # 首页预检：可见区域笔记全早于start_date则快速跳过
    visible_ids = set()
    visible_raw = cdp.eval("""
        (()=>{
            let ids=[];
            document.querySelectorAll('a[href*="/explore/"]').forEach(a=>{
                let m=a.href.match(/([0-9a-f]{24})/);
                if(m) ids.push(m[1]);
            });
            return ids;
        })()
    """, sid, timeout=5)
    if visible_raw:
        visible_ids = set(re.findall(r'[0-9a-f]{24}', str(visible_raw)))
    if visible_ids:
        newest_visible = max(
            (nid for nid in visible_ids if id_to_date(nid)),
            key=lambda n: id_to_date(n),
            default=None
        )
        if newest_visible:
            nd = id_to_date(newest_visible)
            if nd and nd < start_date:
                print(f"  首页预检: 最新{nd} < {start_date}，跳过滚动", flush=True)
                cdp.close_target(tid)
                # 增量模式：保留旧笔记数据
                if is_incremental and xhs_id in old_notes_map:
                    old_notes = sorted(old_notes_map[xhs_id].values(), key=lambda x: x['d'], reverse=True)
                    _upsert(results, {
                        "nickname": nick, "xhs_id": xhs_id, "url": url,
                        "total": len(visible_ids),
                        "june": len(old_notes), "june_notes": old_notes,
                        "abnormal": False
                    })
                    print(f"  保留旧数据: {len(old_notes)}条", flush=True)
                else:
                    _upsert(results, {
                        "nickname": nick, "xhs_id": xhs_id, "url": url,
                        "total": len(visible_ids),
                        "june": 0, "june_notes": [],
                        "abnormal": False
                    })
                done_ids.add(xhs_id)
                safe_save(results)
                time.sleep(random.uniform(1, 3))
                continue

    # 滚动提取 — 随机化滚动距离/间隔，模拟人类行为
    all_ids = set()
    prev, stable = 0, 0
    for s in range(50):
        scroll_px = random.randint(400, 1200)        # 随机滚动距离
        sleep_t = random.uniform(0.3, 2.0)           # 随机滚动间隔（激进版）
        if stable > 2:
            sleep_t += 1.0                            # 快到底时放慢
        cdp.eval(f'window.scrollBy(0,{scroll_px})', sid, timeout=5)
        time.sleep(sleep_t)

        # 10%概率模拟往回滚（人类偶尔回看）
        if random.random() < 0.1:
            back_px = random.randint(100, 300)
            cdp.eval(f'window.scrollBy(0,-{back_px})', sid, timeout=5)
            time.sleep(random.uniform(0.3, 1.0))

        ids = cdp.eval(EXTRACT, sid, timeout=10)
        if isinstance(ids, list):
            all_ids.update(ids)

        # 15%概率"阅读停留"（模拟人在看笔记内容）
        if len(all_ids) > prev and random.random() < 0.15:
            pause = random.uniform(1.5, 5.0)
            time.sleep(pause)

        if len(all_ids) == prev:
            stable += 1
            if stable >= 8: break
        else:
            stable = 0
        prev = len(all_ids)
        # 超出起始日期范围时停止
        if len(all_ids) > 10:
            oldest_hex = min(n[:8] for n in all_ids)
            oldest_date = id_to_date(oldest_hex + '0'*16)
            if oldest_date and oldest_date < start_date:
                print(f"  到{oldest_date}停止{s+1}次滚动", flush=True)
                break
        if s > 0 and s % 15 == 0:
            print(f"  {s}次滚动 {len(all_ids)}条", flush=True)

    # 关闭tab释放资源
    cdp.close_target(tid)

    june_notes = sorted(
        [{"id": n, "d": id_to_date(n)} for n in all_ids
         if id_to_date(n) and id_to_date(n) >= start_date],
        key=lambda x: x['d'], reverse=True
    )

    # 增量模式：合并旧数据
    if is_incremental and xhs_id in old_notes_map:
        merged = dict(old_notes_map[xhs_id])
        new_count = sum(1 for n in june_notes if n['id'] not in merged)
        for n in june_notes:
            merged[n['id']] = n
        june_notes = sorted(merged.values(), key=lambda x: x['d'], reverse=True)
        print(f"  合并后: {len(june_notes)}条（旧{len(old_notes_map[xhs_id])}+新{new_count}）", flush=True)
    else:
        print(f"  {start_date}起: {len(june_notes)}条 / 总: {len(all_ids)}条", flush=True)

    _upsert(results, {
        "nickname": nick,
        "xhs_id": xhs_id,
        "url": url,
        "total": len(all_ids),
        "june": len(june_notes),
        "june_notes": june_notes,
        "abnormal": abnormal
    })
    done_ids.add(xhs_id)

    # 实时保存进度（原子替换+重试，规避文件被监视/同步锁定的间歇冲突）
    safe_save(results)

    # 账号间随机等待 5-15 秒（激进版，模拟人类切换账号的间歇）
    wait = random.uniform(5, 15)
    print(f"  等待 {wait:.0f}秒...", flush=True)
    time.sleep(wait)

cdp.close()

print(f"\n[完成] 共 {len(results)} 个账号（{start_date}起）")
print(f"结果已保存: {RESULTS_FILE}")
