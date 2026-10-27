"""回滚 —— 出事的时候把一切退回去（2026-10-27）。

三件事，按顺序做，每一步都能单独用：

    python 回滚.py              # 只看会做什么，不动手（默认）
    python 回滚.py --apply      # 真的做

做的是：
    1. 放一个「停用工具闸」开关 —— 工具闸立刻什么都不拦（不用重启、不用卸载）
    2. 备份当前的 body/ 到 beifen/回滚-<时间>/
    3. 如果给了 --dsh-backup <路径>，把 ~/.dsh 从备份恢复回去（会先把它现在这份另存）

**卸插件只能在 DSH 界面里做**（插件页 → 那个插件 → 卸载 → 重启），脚本碰不了那一步，
最后会把步骤打印出来。

用法示例：
    python 回滚.py --apply --dsh-backup D:\\备份\\dsh-20261027
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
BODY = ROOT / "body"
开关 = BODY / "renwu" / "停用工具闸"
DSH = Path.home() / ".dsh"


def 说(文本: str) -> None:
    print(文本)


def 做开关(应用: bool) -> None:
    开关.parent.mkdir(parents=True, exist_ok=True)
    if 开关.exists():
        说(f"· 工具闸总开关：已经在了（{开关}）")
        return
    if not 应用:
        说(f"· 会新建总开关：{开关}（工具闸从此什么都不拦）")
        return
    开关.write_text(
        "这个文件存在 = 工具闸全部放行。\n"
        f"建于 {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        "想恢复拦：把这个文件删掉，重启 DSH。\n",
        encoding="utf-8",
    )
    说(f"· 已建总开关：{开关} —— 工具闸现在什么都不拦了（不用重启）")


def 备份本体(应用: bool) -> None:
    if not BODY.exists():
        说("· 没有 body/，跳过备份")
        return
    目标 = ROOT / "beifen" / f"回滚-{datetime.now():%Y%m%d-%H%M%S}"
    if not 应用:
        说(f"· 会把现在的 body/ 复制一份到 {目标}")
        return
    目标.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BODY, 目标)
    说(f"· 已备份 body/ → {目标}")


def 恢复dsh(来源: Path | None, 应用: bool) -> None:
    if 来源 is None:
        说("· 没给 --dsh-backup，跳过 ~/.dsh 恢复")
        return
    if not 来源.exists():
        说(f"· 备份目录不存在：{来源}")
        return
    if not DSH.exists():
        说(f"· 这台机器上没有 {DSH}（没装过 DSH？），跳过")
        return
    现在 = DSH.parent / f"dsh-回滚前-{datetime.now():%Y%m%d-%H%M%S}"
    if not 应用:
        说(f"· 会把现在的 {DSH} 另存为 {现在}，再用 {来源} 覆盖回去")
        return
    shutil.move(str(DSH), str(现在))
    shutil.copytree(来源, DSH)
    说(f"· 已恢复 ~/.dsh ← {来源}（旧的另存在 {现在.name}）")


def 卸插件提示() -> None:
    说("")
    说("还剩一步只能在界面里做（脚本碰不了 DSH 的插件注册）：")
    说("  1. 打开 DSH → 插件页")
    说("  2. 找到「dsh-toolgate」和「dsh-handin-bubble」→ 卸载")
    说("  3. 重启 DSH")
    说("  4. （可选）把本目录整个删掉 —— body/ 是你的数据，删之前自己看清楚")


def main() -> int:
    ap = argparse.ArgumentParser(description="分身术回滚")
    ap.add_argument("--apply", action="store_true", help="真的执行（默认只看）")
    ap.add_argument("--dsh-backup", type=Path, default=None, help="之前备份的 ~/.dsh 目录")
    ap.add_argument("--keep-body", action="store_true", help="不备份 body/")
    a = ap.parse_args()

    说("分身术 · 回滚" + ("（真的要做）" if a.apply else "（只是看看，加 --apply 才动手）"))
    说("")
    做开关(a.apply)
    if not a.keep_body:
        备份本体(a.apply)
    恢复dsh(a.dsh_backup, a.apply)
    卸插件提示()
    说("")
    说("做完这些，你的鱼还是你原来那条 —— 记忆、人设、会话都在原来的位置。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
