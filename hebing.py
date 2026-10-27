"""本体仓库的合并工具：把 inbox 里的提案合进目标文件，归档并 git 提交。

用法：
    python body/hebing.py --list    看提案
    python body/hebing.py --dry     演练（只打印要改什么）
    python body/hebing.py           真合并（追加类自动合；修改类只打印等点头）

规矩见 body/shuoming.md。
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import pathlib
import re
import shutil
import subprocess

BODY = pathlib.Path(__file__).resolve().parent
ROOT = BODY.parent
INBOX = BODY / "daishen"
MERGED = BODY / "yishen"


@dataclasses.dataclass
class Proposal:
    path: pathlib.Path
    meta: dict
    content: str

    @property
    def kind(self) -> str:
        return str(self.meta.get("kind", "")).strip()

    @property
    def target(self) -> str:
        return str(self.meta.get("target", "")).strip()


def 剥说明(text: str) -> str:
    """提案里「要改什么 / 为什么 / 证据 / 以下是正文」这些是给人看的说明，
    合并时不该进正文（2026-10-26 栽过两次）。"""
    lines = text.splitlines()
    # 优先找「以下是……正文」后面那条分隔线
    for i, line in enumerate(lines):
        if "以下是" in line and ("正文" in line or "内容" in line):
            j = i + 1
            while j < len(lines) and lines[j].strip() in ("", "---", "***"):
                j += 1
            return "\n".join(lines[j:]).strip()
    # 没有就删掉开头的说明行（要改什么/为什么/证据/来源…），保留第一个标题或第一条正文
    out, skipping = [], True
    说明前缀 = ("要改什么", "为什么", "证据", "来源", "影响", "风险", "怎么做", "提议", "备注")
    for line in lines:
        t = line.strip()
        if skipping and (not t or t.startswith(说明前缀) or t.startswith("```") is False and t.startswith("*") and "：" in t):
            continue
        if skipping and (t.startswith("#") or t.startswith("- ") or t.startswith(">")):
            skipping = False
        out.append(line)
    return "\n".join(out).strip()


def parse(path: pathlib.Path) -> Proposal | None:
    text = path.read_text(encoding="utf-8-sig")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = m.group(2).strip()
    body = 剥说明(body)
    return Proposal(path=path, meta=meta, content=body)


def proposals() -> list[Proposal]:
    out = []
    for p in sorted(INBOX.glob("*.md")):
        if p.name.startswith("_"):
            continue
        pr = parse(p)
        if pr:
            out.append(pr)
    return out


def git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # pragma: no cover
        return f"git 失败: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--review", default="", help="要处理哪个提案（文件名，或留空=全部）")
    ap.add_argument("--by", default="", help="审核人：只能填「主人」或「大肥鱼」")
    ap.add_argument("--reject", action="store_true", help="驳回（不合并）：把理由写进审核区，文件挪到 daishen/_已驳回/")
    ap.add_argument("--why", default="", help="驳回理由（配 --reject 用）")
    a = ap.parse_args()

    items = proposals()
    if a.review:
        items = [p for p in items if p.path.name == a.review or a.review in p.path.name]
    if a.list or not items:
        print(f"待合并 {len(items)} 条")
        for pr in items:
            print(f"  {pr.path.name}\n    from={pr.meta.get('from')} kind={pr.kind} target={pr.target}")
        return 0

    # 审核人闸：没写 --by 或写了别人一律不动手
    # 为什么：每个窗口都自称「我」，分身很容易顺手批了自己的提案（2026-10-26 主人指出）
    reviewer = a.by.strip()
    if reviewer not in ("主人", "大肥鱼"):
        print("拒绝合并：必须用 --by 指定审核人，而且只能是「主人」或「大肥鱼」。")
        print("分身不能审自己的提案 —— 请把提案转述给主人，或者交回主窗口。")
        return 3
    for pr in items:
        who = str(pr.meta.get("from", "")).strip()
        if who and who == reviewer:
            print(f"拒绝合并：{pr.path.name} 是 {who} 提的，同一个人不能自己审自己。")
            return 4

    if a.reject:
        if not a.why.strip():
            print("驳回要写理由：--why \"为什么驳\"")
            return 5
        驳 = BODY / "daishen" / "_已驳回"
        驳.mkdir(parents=True, exist_ok=True)
        for pr in items:
            t = pr.path.read_text(encoding="utf-8")
            if "## 审核区" not in t:
                t += "\n## 审核区（提案人一律不要填）\n"
            t = t.rstrip() + f"\n\n- 驳回（{reviewer}，{__import__('datetime').date.today()}）：{a.why.strip()}\n"
            target = 驳 / pr.path.name
            target.write_text(t, encoding="utf-8")
            pr.path.unlink()
            print(f"已驳回：{pr.path.name} → daishen/_已驳回/（理由：{a.why.strip()}）")
        return 0

    MERGED.mkdir(exist_ok=True)
    done, skipped = [], []
    for pr in items:
        if not pr.target:
            skipped.append((pr, "缺 target"))
            continue
        dst = BODY / pr.target
        if pr.kind == "追加":
            if a.dry:
                print(f"[dry] 追加到 {pr.target}：\n{pr.content[:200]}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                with dst.open("a", encoding="utf-8") as f:
                    f.write(pr.content + "\n")
                # 审核区记录：谁审的、结论、日期（2026-10-27 主人要求）
                try:
                    import datetime as _dt
                    文 = pr.path.read_text(encoding="utf-8")
                    if "## 审核区" not in 文:
                        文 += "\n## 审核区（提案人一律不要填）\n"
                    文 = 文.rstrip() + (
                        f"\n\n- reviewed_by: {reviewer}\n"
                        f"- decision: 合并\n"
                        f"- note: 追加进 {pr.target}（{_dt.date.today()}）\n")
                    pr.path.write_text(文, encoding="utf-8")
                except Exception:
                    pass
                shutil.move(str(pr.path), MERGED / pr.path.name)
                done.append(pr)
        else:
            print(f"[待点头] {pr.path.name} kind={pr.kind} target={pr.target}\n{pr.content[:300]}\n")
            skipped.append((pr, "修改类要人点头"))

    if not a.dry and done:
        git("add", "-A")
        msg = "body: 合并 " + ", ".join(p.path.name for p in done)
        print(git("commit", "-m", msg)[:400])
    print(f"合并 {len(done)} 条，待处理 {len(skipped)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
