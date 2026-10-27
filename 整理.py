"""分身术 · 整理：把工作区里散落的东西分盒。

只出清单，人点头才动。

用法：
    python 整理.py                # 出清单 body/cankao/整理清单.md（不动任何文件）
    python 整理.py --apply        # 照清单搬（只移动，不删除；重名自动加序号）

分盒规则（可以照着改）：
    图片 → jietu/<日期>/      （成品图/图标/封面 → tupian/）
    音频 → sheng/            视频 → luxiang/
    日志 → rizhi/            备份 → beifen/
    临时（tmp/out/dist 等）→ linshi/
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
清单 = ROOT / "body" / "cankao" / "整理清单.md"
日志 = ROOT / "beifen" / "整理日志.jsonl"

图片 = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
音频 = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
视频 = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
成品图关键词 = ("架构图", "头像", "icon", "图标", "壁纸", "cover", "封面", "logo")
临时目录名 = {"tmp", "temp", "out", "dist", "build", "rvc-out", "rec-frames", "output"}
不碰 = {"body", "beifen", "jietu", "sheng", "luxiang", "rizhi", "tupian", "linshi", ".git", "node_modules"}


def 归宿(p: Path) -> Path | None:
    if p.is_dir():
        if p.name in 临时目录名:
            return ROOT / "linshi" / p.name
        if p.name.startswith(("backup", "bak", "_bak")):
            return ROOT / "beifen" / p.name
        return None
    ext = p.suffix.lower()
    if ext in 图片:
        if any(k in p.name for k in 成品图关键词):
            return ROOT / "tupian" / p.name
        day = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
        return ROOT / "jietu" / day / p.name
    if ext in 音频:
        return ROOT / "sheng" / p.name
    if ext in 视频:
        return ROOT / "luxiang" / p.name
    if ext == ".log":
        return ROOT / "rizhi" / p.name
    # 一堆临时脚本：.tmp-*、_tmp*、temp*
    if p.name.startswith((".tmp", "_tmp", "tmp-", "temp-")):
        return ROOT / "linshi" / p.name
    return None


def 收集() -> list[tuple[Path, Path]]:
    moves = []
    for p in sorted(ROOT.iterdir()):
        if p.name in 不碰 or p.name.startswith("."):
            continue
        if p.name in {"AGENTS.md", "README.md", "init.py", "导入.py", "整理.py", "panel.py", "panel-index.html"}:
            continue
        t = 归宿(p)
        if t and t != p:
            moves.append((p, t))
    return moves


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    moves = 收集()
    if not moves:
        print("工作区挺整齐，没什么要搬的")
        return 0

    if not a.apply:
        清单.parent.mkdir(parents=True, exist_ok=True)
        行 = ["# 工作区整理清单\n", f"> 共 {len(moves)} 项。**看过再 --apply。**\n",
              "| 现在 | 搬到 | 大小 |", "|---|---|---|"]
        for s, t in moves:
            size = (sum(f.stat().st_size for f in s.rglob("*") if f.is_file()) if s.is_dir() else s.stat().st_size) // 1024
            行.append(f"| {s.name} | {t.relative_to(ROOT).as_posix()} | {size}KB |")
        清单.write_text("\n".join(行) + "\n", encoding="utf-8")
        print(f"清单：{清单}（{len(moves)} 项，没动文件）")
        return 0

    日志.parent.mkdir(parents=True, exist_ok=True)
    with 日志.open("a", encoding="utf-8") as f:
        for s, t in moves:
            t.parent.mkdir(parents=True, exist_ok=True)
            dst = t
            i = 1
            while dst.exists():
                dst = t.with_name(f"{t.stem}-{i}{t.suffix}")
                i += 1
            try:
                shutil.move(str(s), str(dst))
                f.write(json.dumps({"时间": datetime.now().isoformat(timespec="seconds"),
                                    "从": str(s), "到": str(dst)}, ensure_ascii=False) + "\n")
                print(f"  搬 {s.name} → {dst.relative_to(ROOT)}")
            except Exception as e:
                print(f"  跳过 {s.name}：{e}")
    print(f"完成，日志：{日志}（想倒回按日志一条条搬）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
