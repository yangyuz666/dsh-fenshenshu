"""分身开场自检：我该读什么、不该碰什么、欠没欠交卷。

为什么有：`domains` 现在只是「建议读哪些」，文件系统并不拦 —— 分身照样读得到别人的分区。
既然拦不住，就至少让它一眼看清自己的边界，别糊里糊涂越界。

用法（分身开场第一条命令）：
    python body\\ziji.py            # 按自己的会话名
    python body\\ziji.py 群聊鱼      # 指定会话
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BODY = Path(__file__).resolve().parent
DOMAIN_FILES = {
    "语言": ["lingyu/语言.md", "shenfen/说话.md"],
    "群聊": ["lingyu/群聊.md", "shenfen/梗百科.md"],
    "声音": ["lingyu/声音.md"],
    "工作": ["lingyu/工作.md", "zhishi/"],
    "记忆": ["lingyu/记忆.md", "jiyi/"],
    "梗库": ["lingyu/梗库.md", "shenfen/梗百科.md"],
}
素材 = {
    "知识库": "zhishi/",
    "梗库": "shenfen/梗百科.md",
    "语料": "yuliao/",
    "表情指路": "zhishi/表情指路.md",
}


def 谁的() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    # 没有参数时，靠最近改过的记忆目录猜（尽力而为）
    cand = [d for d in (BODY / "jiyi").iterdir() if d.is_dir()]
    if not cand:
        return ""
    return max(cand, key=lambda d: max((f.stat().st_mtime for f in d.rglob("*") if f.is_file()), default=0)).name


def main() -> int:
    名 = 谁的()
    if not 名:
        print("不知道你是谁。用法：python body\\ziji.py <会话名>")
        return 1
    f = BODY / "huihua" / f"{名}.json"
    if not f.exists():
        print(f"没有「{名}」这间屋的档案（body/huihua/{名}.json 不存在）")
        return 1
    d = json.loads(f.read_text(encoding="utf-8"))
    doms = d.get("domains") or ([d["domain"]] if d.get("domain") else [])

    print(f"我是：{名}")
    print(f"身份：{d.get('role', '')}    分区：{'、'.join(doms) or '（没勾）'}")
    print(f"窗口：{'在' if d.get('window') else '不在（DSH 里没有这个会话）'}")
    print()
    print("我该读的文件：")
    for dom in doms:
        for rel in DOMAIN_FILES.get(dom, [f"（{dom} 没有对应文件）"]):
            p = BODY / rel
            size = ""
            if p.is_file():
                size = f"（{p.stat().st_size / 1024:.1f}KB）"
            elif p.is_dir():
                n = len(list(p.rglob("*")))
                size = f"（目录，{n} 项）"
            print(f"  - body/{rel}{size}")
    extra = [k for k in 素材 if k in doms]
    if extra:
        print("  素材库：")
        for k in extra:
            print(f"  - body/{素材[k]}")

    别人 = [x for x in DOMAIN_FILES if x not in doms]
    print()
    print(f"没勾的分区（别去动）：{'、'.join(别人) or '无'}")
    print("  提醒：文件系统不拦，读了没人当场发现 —— 但记忆里提到别家内容，巡检会看出来。")
    print()
    print("工具也是按分区裁的：上面没勾的分区对应的工具，我这边直接没有。")
    print("  调用报 unknown tool / 工具突然消失：先看上面这份分区。")
    print("    · 没勾 → 是分区的事，说一句「不在我工作范围」就行，别绕")
    print("    · 勾了却还是用不了 → 可能真故障：写一条进 body/jianyi/<自己>.md，别自己修，等主窗口查")
    print()
    print("开场还需看的：body/mulu.md；欠账清单 body/renwu/_催交.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
