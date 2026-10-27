"""分身术 · 初始化：把本体骨架铺出来。

用法：
    python init.py                # 在当前目录铺 body/ 骨架
    python init.py D:\\我的鱼       # 指定目录
    python init.py --dry          # 只看会建什么，不动手

规矩：
- 只创建，不覆盖：已存在的文件一律跳过
- 骨架是空的，注释写清每个文件该填什么
"""
from __future__ import annotations

import sys
from pathlib import Path

域 = {
    "语言": "怎么说话：嘴、句式、长度、禁语。填你怎么讲话、不爱听什么、被问该怎么答。",
    "群聊": "在群里怎么活：哪些群、什么频率、能不能复读、哪些话不说。",
    "声音": "发语音、唱歌、声线怎么调（没有语音就先留空）。",
    "工作": "修机器、装插件、跑脚本时踩过的坑和规矩。",
    "记忆": "管本体：记忆怎么写、提案怎么审、什么不许改。",
}

目录 = [
    "shenfen", "lingyu", "jiyi", "jianyi", "daishen", "jinqi",
    "zhishi", "yuliao", "gongju", "renwu", "huihua", "cankao",
]

骨架文件 = {
    "shenfen/人设.md": """# 人设（正本）

> 这是你自己的脸。改之前想清楚：这改的不是文字，是说话的样子。

## 我是谁

（名字、形象、住哪、不是什么）

## 怎么说话

（句子长短、断句方式、有没有口头禅、什么时候嘴硬、什么时候认怂）

## 底线

（不装人、不编造做过的事……）
""",
    "shenfen/自我.md": """# 自我

> 我认的名字、我定的规矩、我拒绝过什么。

## 名字

## 我定的

## 我拒绝过的
""",
    "shenfen/说话.md": """# 说话细则

> 语言域里放不下的细节写这儿：具体句式、禁语清单、被问到某类问题该怎么答。
""",
    "mulu.md": """# 目录

> 开场先看这一份，按需再翻别的。

| 要干什么 | 翻哪里 |
|---|---|
| 怎么说人话 | `lingyu/语言.md` |
| 在群里怎么活 | `lingyu/群聊.md` |
| 说话 / 唱歌 | `lingyu/声音.md` |
| 修机器、插件 | `lingyu/工作.md` |
| 管本体、审提案 | `lingyu/记忆.md` |

## 硬规矩

- 分身只能写 `jiyi/<自己>/`、`jianyi/<自己>.md`、`daishen/`，别的只读
- 改正文要投 `daishen/`，本体审过才合并
- 分身不能审自己的提案
""",
    "jiyi/README.md": "# 记忆\n\n每个会话一个子目录，只追加，不覆盖。\n",
    "jianyi/README.md": "# 建议栏\n\n一行一条，只追加。格式：`- [日期] 发现的问题 —— 建议怎么改（可选）`\n",
    "daishen/README.md": "# 提案区\n\n要改正文就投这里，本体审过才合并。开头写 from / kind / target。\n",
    "jinqi/README.md": "# 近期事件\n\n所有窗口都写、都能读。主窗口定期整理。\n",
    "huihua/README.md": "# 会话档案\n\n一间屋一个 json：`{\"session\": \"名字\", \"role\": \"主窗口|工作|语言\", \"domains\": [\"语言\"]}`\n",
    "renwu/_催交.md": "# 催交清单\n\n干了活没交卷的写这儿，谁的名字谁补。\n",
    "shenfen/梗百科.md": """# 梗库

> 用过的梗、出处、怎么用才不尬。一条一行。
""",
    "zhishi/表情指路.md": """# 表情指路

> 图库太大，塞不进分区。这份只写「什么场合发哪张、文件在哪」，要哪张按路径取。

| 什么时候用 | 文件路径 |
|---|---|
| （例）被夸、要卖萌 | `~/图库/happy/xxx.png` |
""",
    "quanxian.md": """# 写权限表

| 谁能写 | 写哪儿 |
|---|---|
| 分身 | `jiyi/<自己>/`、`jianyi/<自己>.md`、`daishen/`、`jinqi/` |
| 本体（主窗口） | 全部 |

正文（`shenfen/`、`lingyu/`）只能通过提案改。
""",
}



def 提醒跑错地方(根: Path) -> bool:
    """在当前目录看到「旁边已经有 body/」就提醒一声 —— 有人会跑错目录，
    然后在空目录里建了一套新的，打开发现鱼"失忆了"（其实旧的那套还在）。
    返回 True 表示已提醒过、可以继续。
    """
    if (根 / "body").exists():
        return False
    候选 = []
    for up in [根.parent, 根.parent.parent]:
        if (up / "body").exists():
            候选.append(up / "body")
    if not 候选:
        return False
    print("⚠  注意：这里没有 body/，但上面这些地方有：")
    for c in 候选:
        print("     ", c)
    print("   你要是在错的目录跑，就会在空地方建一套新的 —— 打开发现鱼\"失忆了\"。")
    print("   确认要在这里新建，就再跑一次加 --yes。")
    return True


def main() -> int:
    import sys as _sys
    根 = Path.cwd()
    if 提醒跑错地方(根) and "--yes" not in _sys.argv:
        return 2
    dry = "--dry" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    根 = Path(args[0]).resolve() if args else Path.cwd()
    body = 根 / "body"

    print(f"目标：{body}")
    if dry:
        print("（--dry：只看，不动手）\n")

    for d in 目录:
        p = body / d
        if not dry:
            p.mkdir(parents=True, exist_ok=True)
        print(f"  目录 {p.relative_to(根)}")

    for rel, 内容 in 骨架文件.items():
        p = body / rel
        if p.exists():
            print(f"  跳过（已存在）body/{rel}")
            continue
        if not dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(内容, encoding="utf-8")
        print(f"  文件 body/{rel}")

    for 名, 说明 in 域.items():
        p = body / "lingyu" / f"{名}.md"
        if p.exists():
            print(f"  跳过（已存在）body/lingyu/{名}.md")
            continue
        if not dry:
            p.write_text(f"# {名}\n\n> {说明}\n\n（在这里写）\n", encoding="utf-8")
        print(f"  文件 body/lingyu/{名}.md")

    print("\n骨架好了。下一步：")
    print("  1. 填 body/shenfen/人设.md（你的鱼怎么说话）")
    print("  2. 跑 python 导入.py <你的旧资料目录> 出迁移清单")
    print("  3. 跑 python 整理.py 出工作区整理清单")
    print("  4. 起面板：python panel.py（127.0.0.1:9888）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
