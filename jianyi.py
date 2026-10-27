"""建议栏工具：汇总各会话提交的建议，或者给某条标状态。

用法：
    python body/jianyi.py                 # 看所有建议（未处理的标出来）
    python body/jianyi.py --pending       # 只看还没标状态的
    python body/jianyi.py --file 群聊鱼    # 看某一间屋的
    python body/jianyi.py --mark 群聊鱼 3 已采纳   # 给第 3 条标状态（只有主窗口/主人能标）
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BODY = Path(__file__).resolve().parent
SUG = BODY / "jianyi"
ITEM = re.compile(r"-\s*\[(\d{4}-\d{2}-\d{2})\]\s*(.+)")


def items(path: Path) -> list[tuple[int, str, str, bool]]:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = ITEM.search(line)
        if not m:
            continue
        import re as _re
        done = bool(_re.search(r"\s*→\s*(已看|已采纳|已修|不收|驳回|重复)", line))
        out.append((i, m.group(1), m.group(2).strip(), done))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", action="store_true", help="只看没标状态的")
    ap.add_argument("--file", default="", help="只看某一间屋")
    ap.add_argument("--mark", nargs=3, metavar=("会话", "行号", "状态"))
    a = ap.parse_args()

    if a.mark:
        who, lineno, status = a.mark
        p = SUG / f"{who}.md"
        if not p.exists():
            print("没有这间屋的建议栏:", who)
            return 2
        lines = p.read_text(encoding="utf-8").splitlines()
        idx = int(lineno) - 1
        if not (0 <= idx < len(lines)) or not lines[idx].strip().startswith("-"):
            print("行号不对，先 --file 看看第几行")
            return 3
        import re as _re2
        if not _re2.search(r"\s*→\s*(已看|已采纳|已修|不收|驳回|重复)", lines[idx]):
            lines[idx] = lines[idx].rstrip() + f"  → {status}"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"已标：{who} 第 {lineno} 条 → {status}")
        else:
            print("这条已经标过了")
        return 0

    files = [SUG / f"{a.file}.md"] if a.file else sorted(SUG.glob("*.md"))
    total = pending = 0
    for p in files:
        if p.name.startswith("_"):
            continue
        rows = items(p)
        if not rows:
            continue
        show = [r for r in rows if not r[3]] if a.pending else rows
        if not show:
            continue
        print(f"== {p.stem}")
        for lineno, date, text, done in show:
            flag = "  " if done else "**"
            print(f" {flag} L{lineno} [{date}] {text}")
            total += 1
            if not done:
                pending += 1
    print(f"\n共 {total} 条，待处理 {pending} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
