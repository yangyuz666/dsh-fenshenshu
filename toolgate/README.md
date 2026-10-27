# dsh-toolgate

按 `body/huihua/<会话>.json` 的 `domains` 决定分身能用哪些工具。

## 为什么

`domains` 原来只管「该读哪些文档」，管不住「能用哪些工具」——
测试鱼没勾「表情指路」，照样能调 `send_meme`。这个插件在 `agent/created` 时给那个 agent 挂两样：

1. `tools.guard()` —— 兜底守卫，看见了也跑不了
2. `tools.restrict({ deny })` —— 直接从工具面拿掉

## 规则

| 工具 | 需要分区 |
|---|---|
| `send_meme` / `meme_list` | 表情指路 / 语言 / 群聊（任一） |
| `meme_update` / `learn_meme` / `meme_render` / `sticker_*` | 表情指路 |
| `speak` / `text_to_speech` | 声音 |

- **主窗口（大肥鱼）豁免**，不受影响
- 没有 `huihua` 档案的会话不受限（免得误伤你自己开的窗口）

## 日志

`~/.dsh/toolgate.log`：每次挂载、每条拦截都记一行。