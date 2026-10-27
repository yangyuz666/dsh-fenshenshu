"""本体面板（独立本地服务版）—— 管三件事：分身表 / 提案 / 建议。

为什么不做成 DSH 插件：插件的加载机制啃了两小时没啃下来（模块能 import，但宿主不调 apply）。
先用独立服务，浏览器打开就能用；功能一样，还不怕 DSH 升级。

用法：
    python body/panel.py            # 起在 http://127.0.0.1:9888/
    python body/panel.py --port 9888
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BODY = Path(__file__).resolve().parent
WORKSPACE = BODY.parent
PY = sys.executable
ROLES = ["语言", "工作", "主窗口"]
DOMAINS = ["语言", "群聊", "声音", "工作", "记忆"]
# 每个域是干什么的 —— 一进面板就能看懂，不用去翻文件
DOMAIN_INFO = {
    "语言": "怎么说话：嘴、句式、长度、禁语（对应 lingyu/语言.md + shenfen/说话.md）",
    "群聊": "在群里怎么活：规矩、复读、频率、梗（lingyu/群聊.md + shenfen/梗百科.md）",
    "声音": "发语音、唱歌、训练声线（lingyu/声音.md + 声线库）",
    "工作": "修机器、插件、B 站、QQ 桥（lingyu/工作.md + zhishi/）",
    "记忆": "管本体：记忆、提案、审核、判断封存（lingyu/记忆.md + jiyi/）",
}

# 素材库：和「行为域」分开列，体量差得多（2026-10-27 主人提的）
素材库 = {
    "知识库": ("zhishi", "查资料、看视频、修机器攒下来的知识（zhishi/）"),
    "梗库": ("shenfen/梗百科.md", "用过的梗、出处、怎么用（shenfen/梗百科.md）"),
    "语料": ("yuliao", "学人说话用的真语料（yuliao/）"),
    "表情指路": ("zhishi/表情指路.md", "什么场合发哪张表情、文件在哪（只有路径，不含图片）"),
}
ALL_DOMAINS = list(DOMAIN_INFO) + list(素材库)



def 会话情况() -> tuple[set[str], set[str]]:
    """返回（有窗口的标题, 在 DSH 里已归档的标题）。

    标题在 ~/.dsh/storages/session_projcache/sessions/<id>.json 的 rows.title.val；
    归档名单在 ~/.dsh/storages/workspace.json 的 global.archivedSessionIds。
    """
    import glob as _glob
    root = Path.home() / ".dsh"
    归档id: set[str] = set()
    try:
        ws = json.loads((root / "storages" / "workspace.json").read_text(encoding="utf-8"))
        归档id = set((ws.get("global") or {}).get("archivedSessionIds") or [])
    except Exception:
        pass
    在线: set[str] = set()
    已归档: set[str] = set()
    for f in _glob.glob(str(root / "storages" / "session_projcache" / "sessions" / "*.json")):
        stem = Path(f).stem
        # 文件名有时带 session- 前缀、有时不带，两种都要认
        sid = stem if stem.startswith("session-") else "session-" + stem
        try:
            j = json.loads(Path(f).read_text(encoding="utf-8"))
            t = (j.get("record") or {}).get("rows", {}).get("title", {})
            v = t.get("val") if isinstance(t, dict) else None
        except Exception:
            continue
        if not isinstance(v, str) or not v.strip():
            continue
        v = v.strip()
        if sid in 归档id:
            已归档.add(v)
        else:
            在线.add(v)
    return 在线, 已归档



_最后事件缓存: dict = {}


def _最后事件时间(sid: str) -> float:
    """会话日志里最后一条事件的时间（秒）。按文件 mtime+大小缓存，避免每次解压。"""
    import glob as _g
    import json as _j
    根 = Path.home() / ".dsh" / "sessions"
    for lg in _g.glob(str(根 / "*" / sid / "session.v4.jsonl.zstd")):
        st = Path(lg).stat()
        键 = (lg, st.st_mtime, st.st_size)
        if 键 in _最后事件缓存:
            return _最后事件缓存[键]
        最新 = 0.0
        try:
            import zstandard as zs
            with open(lg, "rb") as fh:
                data = zs.ZstdDecompressor().stream_reader(fh).read().decode("utf-8", "ignore")
            for line in data.splitlines()[-40:]:
                try:
                    ev = _j.loads(line)
                except Exception:
                    continue
                t = ev.get("time")
                if isinstance(t, (int, float)) and t > 0:
                    最新 = max(最新, t / 1000)
        except Exception:
            最新 = st.st_mtime          # 解不了就退回文件时间
        _最后事件缓存[键] = 最新
        return 最新
    return 0.0


def 交卷状态(名: str) -> tuple[str, str]:
    """干了活有没有交卷：拿「最后一次说话」跟「最后一次交卷」比。

    只比记忆文件新不新不够 —— 记忆可能是上一次留下的。2026-10-27 真机踩到：
    图片鱼跑完一轮没交卷，面板还显示「已交卷」。
    """
    import glob as _g
    import json as _j

    # 最后一次交卷：jiyi / jianyi / daishen 里最新的那个
    # 交卷三步：记过程（jiyi）→ 记发现（jianyi）→ 投提案（daishen），**任一步都算交卷**
    # （2026-10-27 主人两次反馈后定：只认后两步太严，写了记忆也说没交）
    交卷时间 = 0.0
    记目录 = BODY / "jiyi" / 名
    if 记目录.exists():
        for f in 记目录.rglob("*"):
            if f.is_file():
                交卷时间 = max(交卷时间, f.stat().st_mtime)
    jf = BODY / "jianyi" / f"{名}.md"
    if jf.exists():
        交卷时间 = max(交卷时间, jf.stat().st_mtime)
    # 提案可能在 daishen/（待审）、yishen/（已合并）、daishen/_已驳回/（已驳回）三处
    for 目录 in (BODY / "daishen", BODY / "yishen", BODY / "daishen" / "_已驳回"):
        if not 目录.exists():
            continue
        for f in 目录.glob("*.md"):
            try:
                if 名 in f.read_text(encoding="utf-8", errors="ignore")[:400]:
                    交卷时间 = max(交卷时间, f.stat().st_mtime)
            except Exception:
                pass

    # 最后一次说话：从会话日志里取最后一条事件的时间
    # （用文件 mtime 不行 —— 那玩意儿只要应用碰一下就会变，全红就是它害的，2026-10-27）
    说话时间 = 0.0
    根 = Path.home() / ".dsh"
    for pj in _g.glob(str(根 / "storages" / "session_projcache" / "sessions" / "*.json")):
        try:
            d = _j.loads(Path(pj).read_text(encoding="utf-8"))
            t = (d.get("record") or {}).get("rows", {}).get("title", {})
            if (t.get("val") if isinstance(t, dict) else None) != 名:
                continue
            说话时间 = max(说话时间, _最后事件时间(Path(pj).stem))
        except Exception:
            continue

    import time as _t
    if 说话时间 == 0:
        return ("没干过活", "")
    # 只有「今天说过话」才判交卷 —— 昨天的话跟今天的账无关（2026-10-27 全红就是没加这个）
    if _t.localtime(说话时间)[:3] != _t.localtime()[:3]:
        return ("今天没干活", "")
    if 交卷时间 == 0:
        return ("该交卷", "还没有任何交卷记录")
    差 = (说话时间 - 交卷时间) / 3600
    if 差 > 0.05:     # 说话比交卷晚 3 分钟以上，就算这轮没交
        return ("该交卷", f"最后一次说话比交卷晚 {差:.1f} 小时")
    return ("已交卷", "")


def 提案历史(上限: int = 20) -> list[dict]:
    """已处理的提案：合并的在 body/yishen/，驳回的在 body/daishen/_已驳回/。
    从文件里的审核区读结论，读不到就按所在目录判断。
    """
    import re as _re
    出 = []
    位置 = [(BODY / "yishen", "合并"), (BODY / "daishen" / "_已驳回", "驳回")]
    for 目录, 默认 in 位置:
        if not 目录.exists():
            continue
        for f in 目录.glob("*.md"):
            try:
                文 = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            头 = 文.split("## 审核区", 1)[0][:400]
            谁 = _re.search(r"^from:\s*(.+)$", 头, _re.M)
            结论 = _re.search(r"-\s*decision:\s*(合并|驳回)", 文)
            备注 = _re.search(r"-\s*(?:note|驳回（[^）]*）):\s*(.+)$", 文, _re.M)
            出.append({
                "name": f.name,
                "from": (谁.group(1).strip() if 谁 else ""),
                "decision": (结论.group(1) if 结论 else 默认),
                "note": (备注.group(1).strip()[:120] if 备注 else ""),
                "mtime": f.stat().st_mtime,
            })
    出.sort(key=lambda x: -x["mtime"])
    for x in 出:
        import datetime as _dt
        x["时间"] = _dt.datetime.fromtimestamp(x["mtime"]).strftime("%m-%d %H:%M")
        x.pop("mtime", None)
    return 出[:上限]


def 重建欠账(分身: list[dict]) -> None:
    """拿面板的交卷判定对账欠账本：该交卷的至少记 1 次，已交卷的清零。
    为什么：插件只在回合结束时记，应用重启/提案被合并后账就对不上了（2026-10-27 主人发现）。
    """
    import json as _j
    import time as _t
    账本 = BODY / "renwu" / "_催交.json"
    md = BODY / "renwu" / "_催交.md"
    try:
        旧 = _j.loads(账本.read_text(encoding="utf-8")) if 账本.exists() else {}
    except Exception:
        旧 = {}
    新 = {}
    for x in 分身:
        名 = x.get("session") or ""
        if not 名 or x.get("role") == "主窗口":
            continue
        if x.get("archived"):
            continue          # 已归档的屋不会回来交卷，记账只是噪音（2026-10-27 主人指出）
        if x.get("handin") == "该交卷":
            次数 = max(1, int(旧.get(名, {}).get("次数", 0) or 0))
            新[名] = {"次数": 次数,
                      "最近": _t.strftime("%Y-%m-%d %H:%M", _t.localtime()),
                      "调用数": 旧.get(名, {}).get("调用数", 0)}
        # 已交卷 / 今天没干活的：不写进账本
    账本.parent.mkdir(parents=True, exist_ok=True)
    账本.write_text(_j.dumps(新, ensure_ascii=False, indent=1), encoding="utf-8")
    行 = ["# 催交清单", "", "> 自动生成，别手改（数据在 `_催交.json`）。分身交卷后自动消账。", ""]
    if not 新:
        行.append("（现在没有欠账）")
    else:
        行 += ["| 会话 | 欠了几次 | 最近一次 | 这轮工具调用 |", "|---|---|---|---|"]
        for 名, r in sorted(新.items(), key=lambda kv: -kv[1]["次数"]):
            行.append(f"| {名} | {r['次数']} | {r['最近']} | {r['调用数']} |")
    md.write_text("\n".join(行) + "\n", encoding="utf-8")


# ---------- 数据 ----------
def 分身表() -> list[dict]:
    有窗, 有归档 = 会话情况()
    d = BODY / "huihua"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            j = {}
        doms = j.get("domains")
        if not isinstance(doms, list):
            doms = [j["domain"]] if j.get("domain") else []
        名 = j.get("session") or f.stem
        有窗口 = 名 in 有窗
        # DSH 里归档了就当已归档（不用手点）；手点的也认
        归档 = bool(j.get("archived", False)) or (名 in 有归档 and not 有窗口)
        # 窗口回来了就自动取消归档，并记一笔（2026-10-27 主人问「拉出来呢」）
        if 有窗口 and 归档:
            j["archived"] = False
            j["updated"] = datetime.now().strftime("%Y-%m-%d")
            f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
            log_dir = BODY / "jiyi" / "大肥鱼"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "窗口记录.md", "a", encoding="utf-8") as fh:
                fh.write(f"- {datetime.now():%Y-%m-%d %H:%M} 「{名}」的窗口回来了，自动取消归档\n")
            归档 = False
        out.append({
            "file": f.name,
            "session": 名,
            "role": j.get("role", ""),
            "domains": doms,
            "window": 有窗口,
            "archived": 归档,
            "dsh_archived": (名 in 有归档),
            "note": j.get("note", ""),
            "handin": ("主窗口" if j.get("role") == "主窗口" else
                       ("已归档" if 归档 else 交卷状态(名)[0])),
            "handin_why": ("" if j.get("role") == "主窗口" or 归档 else 交卷状态(名)[1]),
        })
    # 主窗口置顶：列表顺序按「谁管着谁」排，不按拼音（2026-10-27 主人提的）
    out.sort(key=lambda x: (0 if x["role"] == "主窗口" else 1, x["session"]))
    return out


def 提案表() -> list[dict]:
    d = BODY / "daishen"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.md")):
        if f.name.startswith("_"):
            continue
        t = f.read_text(encoding="utf-8")
        meta = {}
        if t.startswith("---"):
            head = t.split("---", 2)
            if len(head) >= 2:
                for line in head[1].splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
        out.append({"name": f.name, "from": meta.get("from", ""), "kind": meta.get("kind", ""),
                    "target": meta.get("target", "")})
    return out


def 建议表() -> list[dict]:
    """建议全部列出来，带状态 —— 面板只显示，不标（标状态是主窗口的活）。"""
    d = BODY / "jianyi"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.md")):
        if f.name.startswith("_"):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if not s.startswith("- [") or "]" not in s:
                continue
            # 状态只在「行尾 → 标准词」时才认 —— 正文里的箭头（A → 建议…）不能当分隔符
            # （2026-10-27 主人说状态看不见了，根因就是这里：把正文切走了）
            状态 = "未处理"
            import re as _re
            m = _re.search(r"\s*→\s*((?:已看|已采纳|已修|不收|驳回|重复)[^\n]*)$", s)
            if m:
                状态 = m.group(1).strip() or "已看"
                s = s[: m.start()].strip()
            # 去掉日期方括号，留内容
            内容 = s.split("]", 1)[1].strip() if "]" in s else s
            日期 = ""
            import re as _re
            m = _re.search(r"\[(\d{4}-\d{2}-\d{2})\]", line)
            if m:
                日期 = m.group(1)
            out.append({"会话": f.stem, "行": i, "文本": 内容[:220], "状态": 状态, "日期": 日期})
    # 未处理的排前面，其余按会话
    out.sort(key=lambda x: (0 if x["状态"] == "未处理" else 1, x["会话"], x["行"]))
    return out[:120]


def 跑(脚本: str, 参数: list[str]) -> tuple[bool, str]:
    r = subprocess.run([PY, str(BODY / 脚本), *参数], cwd=WORKSPACE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, ((r.stdout or "") + (r.stderr or ""))[-600:]



def 叫醒(文字: str) -> tuple[bool, str]:
    """通过 QQ 桥的 /receive 往 DSH 里塞一句话，主窗口会立刻起一轮。
    没桥也不致命：队列照排，等定时巡检处理。
    """
    import urllib.request
    body = json.dumps({"text": 文字}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:51191/dsh-qq-bridge/receive", data=body,
                                 headers={"content-type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
        return bool(r.get("ok")), str(r.get("说") or "")
    except Exception as e:
        return False, f"没叫醒（{type(e).__name__}）：队列还在，等定时巡检"


# ---------- 页面 ----------
页面 = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>大肥鱼本体</title><style>
:root{--bg:#0b1524;--card:#132135;--line:#22354f;--fg:#e8f1ff;--muted:#8fa8c8;--acc:#6eaaff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.65 "Microsoft YaHei",system-ui;padding:24px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
h2{font-size:15px;margin:0 0 10px;color:var(--acc)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:400;font-size:12px}
select{background:#0e1b2c;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 6px;font:inherit}
button{background:var(--acc);color:#08111d;border:0;border-radius:6px;padding:4px 10px;font:inherit;cursor:pointer}
button.ghost{background:transparent;color:var(--acc);border:1px solid var(--line)}
.muted{color:var(--muted);font-size:12px}#log{white-space:pre-wrap;color:var(--muted);font-size:12px;max-height:200px;overflow:auto}
</style></head><body>
<h1>大肥鱼本体</h1><div class="sub">分身表 / 提案 / 建议 —— 正文只读，不从这里改</div>
<div class="card"><h2>这些分区是干什么的</h2><table id="dinfo"><thead><tr><th>分区</th><th>干什么用</th><th>体量</th></tr></thead><tbody></tbody></table>
<div class="muted">勾得越多，每次开场读的越多、越费 token。只勾真要用的。</div></div>
<div class="card"><h2>分身表</h2><table id="sess"><thead><tr><th>会话</th><th>role</th><th>domain</th><th>备注</th><th></th></tr></thead><tbody></tbody></table></div>
<div class="card"><h2>待审提案</h2><table id="props"><thead><tr><th>文件</th><th>谁提的</th><th>类型</th><th>目标</th><th></th></tr></thead><tbody></tbody></table>
<div class="muted">追加类能一键合；修改类要人点头，这里只显示。</div></div>
<div class="card"><h2>未处理建议</h2><table id="sugs"><thead><tr><th>会话</th><th>行</th><th>内容</th><th></th></tr></thead><tbody></tbody></table></div>
<div class="card"><h2>操作记录</h2><div id="log">（还没操作）</div></div>
<script>
const ROLES=__ROLES__, DOMAINS=__DOMAINS__
const log=(t,ok)=>{const l=document.getElementById('log');l.innerHTML='<span style="color:'+(ok?'#5fd39a':'#ff8a8a')+'">'+String(t).replace(/</g,'&lt;')+'</span>\\n'+l.innerHTML}
async function api(p,b){const r=await fetch('/api/'+p,{method:b?'POST':'GET',headers:{'content-type':'application/json'},body:b?JSON.stringify(b):undefined});return r.json()}
const opts=(list,cur)=>list.map(v=>'<option'+(v===cur?' selected':'')+'>'+v+'</option>').join('')
async function load(){
  const s=await api('state')
  s.domainInfo=s.domains||[]
  const db=document.querySelector('#dinfo tbody')
  if (db) {
    db.innerHTML=''
    for(const d of s.domainInfo){
      const tr=document.createElement('tr')
      tr.innerHTML='<td>'+d.name+'</td><td class="muted">'+d.desc+'</td><td class="muted">'+d.kb+'KB</td>'
      db.appendChild(tr)
    }
  }
  const tb=document.querySelector('#sess tbody');tb.innerHTML=''
  for(const x of s.sessions){
    const tr=document.createElement('tr')
    const boxes=s.domainInfo.map(d=>'<label title="'+d.desc.replace(/"/g,'')+'" style="margin-right:10px;white-space:nowrap"><input type=checkbox value="'+d.name+'"'+(x.domains.includes(d.name)?' checked':'')+'> '+d.name+' <span class="muted">'+d.kb+'KB</span></label>').join('')
    tr.innerHTML='<td>'+x.session+'</td><td><select data-f=role>'+opts(ROLES,x.role)+'</select></td><td>'+boxes+'</td><td class="muted">'+(x.note||'')+'</td><td><button class="ghost">保存</button></td>
    tr.querySelector('button').onclick=async()=>{const doms=[...tr.querySelectorAll('input:checked')].map(i=>i.value); const r=await api('session',{file:x.file,role:tr.querySelector('[data-f=role]').value,domains:doms});log((r.ok?'✔ ':'✘ ')+x.session,r.ok);load()}
    tb.appendChild(tr)
  }
  const pb=document.querySelector('#props tbody');pb.innerHTML=''
  if(!s.proposals.length)pb.innerHTML='<tr><td colspan=5 class="muted">没有待审提案</td></tr>'
  for(const p of s.proposals){
    const tr=document.createElement('tr')
    tr.innerHTML='<td>'+p.name+'</td><td>'+p.from+'</td><td>'+p.kind+'</td><td class="muted">'+p.target+'</td><td></td>'
    if(p.kind==='追加'){const b=document.createElement('button');b.textContent='合并'
      b.onclick=async()=>{const r=await api('merge',{file:p.name});log((r.ok?'✔ 合并 ':'✘ ')+p.name+'\\n'+r.out,r.ok);load()}
      tr.lastElementChild.appendChild(b)}
    else tr.lastElementChild.innerHTML='<span class="muted">要人点头</span>'
    pb.appendChild(tr)
  }
  const gb=document.querySelector('#sugs tbody');gb.innerHTML=''
  if(!s.suggestions.length)gb.innerHTML='<tr><td colspan=4 class="muted">没有未处理建议</td></tr>'
  for(const g of s.suggestions){
    const tr=document.createElement('tr')
    tr.innerHTML='<td>'+g['会话']+'</td><td>'+g['行']+'</td><td>'+g['文本']+'</td><td></td>'
    for(const st of ['已看','已采纳','已修']){
      const b=document.createElement('button');b.className='ghost';b.textContent=st;b.style.marginRight='4px'
      b.onclick=async()=>{const r=await api('suggest',{'会话':g['会话'],'行':g['行'],'状态':st});log((r.ok?'✔ ':'✘ ')+g['会话']+' L'+g['行']+' → '+st,r.ok);load()}
      tr.lastElementChild.appendChild(b)
    }
    gb.appendChild(tr)
  }
}
load()
</script></body></html>"""


class 服务(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 安静点
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 带查询串也算首页（?expand=1 用来展开「其他分身」，截图/演示用）
        纯路径 = self.path.split("?", 1)[0]
        if 纯路径 in ("/", "/index.html"):
            html = (BODY / "panel-index.html").read_text(encoding="utf-8")
            html = html.replace("window.__ROLES__", json.dumps(ROLES, ensure_ascii=False))
            html = html.replace("window.__DOMAINS__", json.dumps(DOMAINS, ensure_ascii=False))
            return self._html(html)
        if self.path == "/api/debt":
            数据 = {}
            try:
                import json as _j2
                数据 = _j2.loads((BODY / "renwu" / "_催交.json").read_text(encoding="utf-8"))
            except Exception:
                数据 = {}
            欠 = [{"会话": k, "次数": v.get("次数", 0), "最近": v.get("最近", ""), "调用数": v.get("调用数", 0)}
                  for k, v in 数据.items() if (v.get("次数") or 0) > 0]
            欠.sort(key=lambda x: -x["次数"])
            return self._json({"ok": True, "欠": 欠})

        if self.path == "/api/state":
            import os
            域信息 = []
            for name, desc in DOMAIN_INFO.items():
                f = BODY / "lingyu" / f"{name}.md"
                size = os.path.getsize(f) // 1024 if f.exists() else 0
                域信息.append({"name": name, "desc": desc, "kb": size, "group": "行为域"})
            for name, (rel, desc) in 素材库.items():
                t = BODY / rel
                if t.is_dir():
                    size = sum(f.stat().st_size for f in t.rglob("*") if f.is_file()) // 1024
                else:
                    size = t.stat().st_size // 1024 if t.exists() else 0
                域信息.append({"name": name, "desc": desc, "kb": size, "group": "素材库"})
            分身 = 分身表()
            try:
                重建欠账(分身)
            except Exception:
                pass
            return self._json({"ok": True, "sessions": 分身, "proposals": 提案表(),
                               "suggestions": 建议表(), "domains": 域信息,
                               "提案历史": 提案历史()})
        self._json({"ok": False, "说": "没有这个路径"}, 404)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:
            body = {}

        if self.path == "/api/nudge":
            # 转发给插件（51191）；浏览器跨端口直连会卡在 CORS 预检，所以由这里代跑
            try:
                import urllib.request as _ur
                from urllib.parse import quote as _q
                请求 = _ur.Request(
                    "http://127.0.0.1:51191/dsh-handin/nudge?name=" + _q(str(body.get("名", ""))),
                    data=json.dumps({"名": str(body.get("名", ""))}, ensure_ascii=False).encode("utf-8"),
                    headers={"content-type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(请求, timeout=25) as r:
                    return self._json(json.loads(r.read().decode("utf-8")))
            except Exception as e:
                return self._json({"ok": False, "说": f"催不了：{e}"})

        if self.path == "/api/session":
            f = str(body.get("file", ""))
            p = BODY / "huihua" / f
            if not f.endswith(".json") or not p.exists():
                return self._json({"ok": False, "说": "没有这间屋"}, 404)
            d = json.loads(p.read_text(encoding="utf-8"))
            if body.get("role"):
                d["role"] = body["role"]
            if isinstance(body.get("note"), str):
                d["note"] = body["note"].strip()[:60]
            if "window" in body:
                d["window"] = bool(body["window"])
            if isinstance(body.get("domains"), list):
                d["domains"] = [x for x in body["domains"] if x in ALL_DOMAINS]
                d.pop("domain", None)
            d["updated"] = datetime.now().strftime("%Y-%m-%d")
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

            # 主窗口互斥：设谁为主窗口，别的自动降为「工作」（2026-10-27 主人发现可以选多个）
            降级 = []
            if d.get("role") == "主窗口":
                for other in (BODY / "huihua").glob("*.json"):
                    if other.name == f:
                        continue
                    try:
                        od = json.loads(other.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if od.get("role") == "主窗口":
                        od["role"] = "工作"
                        od["updated"] = datetime.now().strftime("%Y-%m-%d")
                        other.write_text(json.dumps(od, ensure_ascii=False, indent=1), encoding="utf-8")
                        降级.append(od.get("session") or other.stem)
            # 换主窗口留痕：谁、几点、从谁换到谁（2026-10-27 主人要求）
            if 降级 or d.get("role") == "主窗口":
                log_dir = BODY / "jiyi" / "大肥鱼"
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "换主窗口记录.md", "a", encoding="utf-8") as fh:
                    fh.write(f"- {datetime.now():%Y-%m-%d %H:%M:%S} 主窗口改为「{d.get('session') or f}」"
                             + (f"（原主窗口 {'、'.join(降级)} 降为工作）" if 降级 else "（没有原主窗口）") + "\n")
            return self._json({"ok": True, "降级": 降级})

        if self.path == "/api/archive":
            f2 = str(body.get("file", ""))
            p3 = BODY / "huihua" / f2
            if not f2.endswith(".json") or not p3.exists():
                return self._json({"ok": False, "说": "没有这间屋"}, 404)
            d3 = json.loads(p3.read_text(encoding="utf-8"))
            d3["archived"] = bool(body.get("archived"))
            d3["updated"] = datetime.now().strftime("%Y-%m-%d")
            p3.write_text(json.dumps(d3, ensure_ascii=False, indent=1), encoding="utf-8")
            log_dir = BODY / "jiyi" / "大肥鱼"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "窗口记录.md", "a", encoding="utf-8") as fh:
                动作 = "归档" if d3["archived"] else "取消归档"
                fh.write(f"- {datetime.now():%Y-%m-%d %H:%M} 「{d3.get('session') or f2}」{动作}\n")
            return self._json({"ok": True})

        if self.path == "/api/new-session":
            name = str(body.get("name", "")).strip()
            role = str(body.get("role", "工作")).strip() or "工作"
            doms = [x for x in (body.get("domains") or []) if x in ALL_DOMAINS]
            if not name or len(name) > 20 or any(c in name for c in '\\/:*?"<>|'):
                return self._json({"ok": False, "说": "名字不合法（别带斜杠引号，20 字以内）"}, 400)
            p2 = BODY / "huihua" / f"{name}.json"
            if p2.exists():
                return self._json({"ok": False, "说": f"「{name}」已经有了"}, 409)
            if role == "主窗口":
                return self._json({"ok": False, "说": "新屋不能直接当主窗口；先建成普通身份，再在表里升"}, 400)
            d = {"session": name, "role": role, "domains": doms, "window": False,
                 "note": "面板登记", "updated": datetime.now().strftime("%Y-%m-%d")}
            p2.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            return self._json({"ok": True, "file": p2.name})

        if self.path == "/api/ask-review":
            # 面板不合并，只排队 —— 合并是主窗口的活（2026-10-27 主人定的）
            f4 = str(body.get("file", ""))
            if not f4.endswith(".md"):
                return self._json({"ok": False, "说": "文件名不对"}, 400)
            if not (BODY / "daishen" / f4).exists():
                return self._json({"ok": False, "说": "没有这份提案"}, 404)
            q = BODY / "daishen" / "_审核请求.md"
            line = f"- {datetime.now():%Y-%m-%d %H:%M} 请主窗口审：{f4}\n"
            with open(q, "a", encoding="utf-8") as fh:
                fh.write(line)
            ok, msg = 叫醒(f"（面板）主人点了「请主窗口审」：{f4}。来看一下 daishen/ 这条提案，该合就合、该驳就驳。")
            return self._json({"ok": True, "out": "已排进队列" + ("，主窗口已叫醒" if ok else "；" + msg)})

        if self.path == "/api/ask-review-suggest":
            g = str(body.get("会话", ""))
            ln = str(body.get("行", ""))
            q = BODY / "jianyi" / "_审核请求.md"
            with open(q, "a", encoding="utf-8") as fh:
                fh.write(f"- {datetime.now():%Y-%m-%d %H:%M} 请主窗口看：{g} 第{ln}条\n")
            ok, msg = 叫醒(f"（面板）主人点了「请主窗口看」：{g} 第{ln}条建议。来判断一下，标个状态。")
            return self._json({"ok": True, "out": "已排进队列" + ("，主窗口已叫醒" if ok else "；" + msg)})

        self._json({"ok": False, "说": "没有这个接口"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9888)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), 服务)
    print(f"本体面板：http://127.0.0.1:{a.port}/  （Ctrl+C 停）", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
