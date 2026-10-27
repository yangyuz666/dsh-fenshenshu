"""分身术 · 导入：把旧资料归进分区里。

只出清单，人看过才动手。

用法：
    python 导入.py D:\\我的旧资料                 # 扫描，出 迁移清单.md
    python 导入.py D:\\我的旧资料 --apply         # 照清单复制进 body/
    python 导入.py D:\\我的旧资料 --apply --move  # 改成移动（默认只复制，原文件留着）

规矩：
- 默认**复制**，原文件不动
- 只往 body/lingyu、body/zhishi、body/yuliao、body/shenfen 收；其余不碰
- 判不准的一律标「待定」，不硬塞
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

# 作用对象是「当前目录」——和 init.py 一致：在哪个项目里跑，就导进那个项目的 body/
ROOT = Path.cwd()
BODY = ROOT / "body"
清单 = BODY / "cankao" / "迁移清单.md"
选择文件 = BODY / "cankao" / "迁移选择.json"
问AI = BODY / "cankao" / "待定问AI.md"
AI答 = BODY / "cankao" / "AI判.txt"

文本后缀 = {".md", ".txt", ".json", ".yml", ".yaml"}
跳过目录 = {".git", "node_modules", "__pycache__", ".pytest_cache", "venv", ".venv"}

# 关键词 → 分区。命中多的优先。
规则 = [
    ("语言", ["说话", "语气", "口头禅", "句式", "人设", "人格", "persona", "风格", "禁语"]),
    ("群聊", ["群", "复读", "梗", "贴吧", "社区", "弹幕", "群规"]),
    ("声音", ["声线", "语音", "配音", "朗读", "tts", "音频"]),
    ("工作", ["脚本", "插件", "命令", "部署", "报错", "教程", "笔记", "todo"]),
    ("记忆", ["记忆", "日记", "反思", "成长", "提案", "复盘"]),
]
素材规则 = [
    ("yuliao", ["语料", "样本", "句子", "对话记录", "corpus"]),
    ("zhishi", ["知识", "资料", "教程", "手册", "文档"]),
]


def 判(路: Path, 文: str) -> tuple[str, str]:
    """返回（目标分区, 依据）。判不准给「待定」。"""
    名 = 路.name.lower()
    头 = 文[:2000].lower()
    分 = {"语言": 0, "群聊": 0, "声音": 0, "工作": 0, "记忆": 0}
    依据 = []
    for 区, 词表 in 规则:
        for w in 词表:
            if w in 名 or w in 头:
                分[区] += 1
                依据.append(w)
    if max(分.values()) == 0:
        # 看是不是素材类
        for 盒, 词表 in 素材规则:
            for w in 词表:
                if w in 名 or w in 头:
                    return 盒, f"命中「{w}」"
        return "待定", "没命中关键词"
    区 = max(分, key=分.get)
    return 区, "命中 " + "、".join(sorted(set(依据))[:4])


def 读选择() -> dict:
    try:
        return json.loads(选择文件.read_text(encoding="utf-8"))
    except Exception:
        return {}


def 写选择(d: dict) -> None:
    选择文件.parent.mkdir(parents=True, exist_ok=True)
    选择文件.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def 扫(根: Path, 上限: int = 400) -> list[dict]:
    out = []
    for p in sorted(根.rglob("*")):
        if len(out) >= 上限:
            break
        if not p.is_file() or p.suffix.lower() not in 文本后缀:
            continue
        if any(x in p.parts for x in 跳过目录):
            continue
        if p.stat().st_size > 300_000:
            continue
        try:
            文 = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        目标, 依据 = 判(p, 文)
        out.append({"源": p, "目标": 目标, "依据": 依据, "大小": p.stat().st_size})
    return out


def 写清单(条: list[dict], 根: Path) -> None:
    清单.parent.mkdir(parents=True, exist_ok=True)
    行 = ["# 迁移清单\n",
          f"> 扫描 {根}，共 {len(条)} 个文件。**看过再 apply。**",
          "> 默认只复制不移动，原文件留着。\n",
          "| 源文件 | 建议去 | 依据 | 大小 |",
          "|---|---|---|---|"]
    for x in 条:
        目标 = x["目标"]
        去向 = f"`body/{'lingyu/' + 目标 + '.md' if 目标 in ('语言','群聊','声音','工作','记忆') else 目标 + '/'}`" if 目标 != "待定" else "（待定，人工填）"
        行.append(f"| {x['源'].name} | {去向} | {x['依据']} | {x['大小'] // 1024}KB |")
    行 += ["", "## 怎么用", "",
           "1. 把「待定」那几行改成你要的分区，或者删掉（删掉=不要这个文件）",
           "2. 跑 `python 导入.py <同一个目录> --apply`",
           "3. 复制过去的文件在 `body/` 里，原文件没动"]
    清单.write_text("\n".join(行) + "\n", encoding="utf-8")
    print(f"清单写好：{清单}")


def 执行(条: list[dict], 移动: bool) -> None:
    日志 = BODY / "cankao" / "迁移日志.md"
    done = []
    for x in 条:
        目标 = x["目标"]
        if 目标 in ("语言", "群聊", "声音", "工作", "记忆"):
            去 = BODY / "lingyu" / f"{目标}.md"
            去.parent.mkdir(parents=True, exist_ok=True)
            with 去.open("a", encoding="utf-8") as f:
                f.write(f"\n\n<!-- 从 {x['源'].name} 导入 {datetime.now():%Y-%m-%d} -->\n")
                f.write(x["源"].read_text(encoding="utf-8-sig", errors="ignore")[:20000])
            done.append(x["源"].name)
        elif 目标 in ("yuliao", "zhishi"):
            去 = BODY / 目标 / x["源"].name
            去.parent.mkdir(parents=True, exist_ok=True)
            i = 1
            while 去.exists():
                去 = BODY / 目标 / f"{x['源'].stem}-{i}{x['源'].suffix}"
                i += 1
            if 移动:
                shutil.move(str(x["源"]), 去)
            else:
                shutil.copy2(x["源"], 去)
            done.append(去.name)
        else:
            continue
    日志.parent.mkdir(parents=True, exist_ok=True)
    日志.write_text("\n".join(f"- {datetime.now():%Y-%m-%d %H:%M} {n}" for n in done) + "\n", encoding="utf-8")
    print(f"处理了 {len(done)} 个文件，日志：{日志}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("目录")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--move", action="store_true", help="剪切（默认复制，原文件留着）")
    ap.add_argument("--pick", action="store_true", help="逐条问「待定」该归哪儿")
    ap.add_argument("--ai", action="store_true", help="把「待定」整理成一张单子，贴给任意 AI 判")
    ap.add_argument("--ai-read", action="store_true", help="读回 AI 的判断（body/cankao/AI判.txt）")
    a = ap.parse_args()

    根 = Path(a.目录).resolve()
    if not 根.exists():
        print("目录不存在：", 根)
        return 1
    条 = 扫(根)

    # 之前选过的（--pick / --ai-read 留下的）在这里生效，随时可以覆盖
    已选 = 读选择()
    for x in 条:
        k = x["源"].name
        if k in 已选:
            x["目标"] = 已选[k]

    # --ai：出问题单（不联网，用你自己的 AI 判）
    待定 = [x for x in 条 if x["目标"] == "待定"]
    if a.ai:
        行 = ["下面是几个文件，我判不准它们该归哪一格。", "",
              "可选格子：语言 / 群聊 / 声音 / 工作 / 记忆 / 知识库(zhishi) / 语料(yuliao) / 跳过",
              "", "请只回「文件名 = 格子」，一行一个，不要解释。", ""]
        for x in 待定:
            头 = x["源"].read_text(encoding="utf-8", errors="ignore")[:200].replace("\n", " ")
            行.append(f"- {x['源'].name}（{x['大小'] // 1024}KB）：{头}")
        问AI.parent.mkdir(parents=True, exist_ok=True)
        问AI.write_text("\n".join(行) + "\n", encoding="utf-8")
        print(f"问题单：{问AI}")
        print(f"把里面内容粘给任意 AI，把回答存成：{AI答}，再跑 --ai-read")
        print(f"（共 {len(待定)} 个待定）")
        return 0

    if a.ai_read:
        if not AI答.exists():
            print(f"没找到 {AI答}")
            return 1
        新 = dict(已选)
        for line in AI答.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if "=" not in line:
                continue
            名, 区 = [t.strip() for t in line.split("=", 1)]
            名 = 名.lstrip("- \ufeff").strip()
            映射 = {"知识库": "zhishi", "语料": "yuliao", "跳过": "待定"}
            if 区:
                新[名] = 映射.get(区, 区)
        写选择(新)
        print(f"AI 的判断已收下（{len(新)} 条），再跑 --pick 可以改，或直接 --apply")
        return 0

    # --pick：把判不准的一个个问清楚（2026-10-27 主人要的）
    if a.pick:
        可选 = "语言/群聊/声音/工作/记忆/知识库/语料/跳过"
        for x in 条:
            if x["目标"] != "待定":
                continue
            print(f"\n文件：{x['源'].name}（{x['大小'] // 1024}KB）")
            print(f"  开局一句话：{x['源'].read_text(encoding='utf-8', errors='ignore')[:60].strip()}")
            现 = x["目标"]
            ans = input(f"  归到哪？（{可选}；回车=跳过，- = 取消回到待定，p=保持）：").strip()
            映射 = {"知识库": "zhishi", "语料": "yuliao", "跳过": "待定"}
            if ans == "-":
                已选.pop(x["源"].name, None)
                x["目标"] = "待定"
            elif ans in ("", "p"):
                if ans == "p":
                    已选[x["源"].name] = 现
            else:
                已选[x["源"].name] = 映射.get(ans, ans)
                x["目标"] = 映射.get(ans, ans)
        if 已选:
            写选择(已选)
            print(f"\n选择已存：{选择文件}（下次跑会自动带上，想改再跑 --pick）")
    if not 条:
        print("没扫到可导入的文本文件")
        return 0
    if not a.apply:
        写清单(条, 根)
        print(f"共 {len(条)} 个，其中判不准 {sum(1 for x in 条 if x['目标'] == '待定')} 个")
        print("看完清单再跑 --apply")
        return 0
    移动 = a.move
    if not a.move:
        ans = input("复制还是剪切？[c=复制 / m=剪切，默认 c]：").strip().lower()
        移动 = ans == "m"
    print(f"\n方式：{'剪切（原文件会消失）' if 移动 else '复制（原文件留着）'}")
    执行(条, 移动)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
