/**
 * dsh-handin-bubble —— 宿主半端：把欠账本读出来给界面用。
 *
 * 只做一件事：GET /dsh-handin/state → { ok, 欠: [{会话, 次数, 最近, 调用数}] }
 * 数据来自 body/renwu/_催交.json（由 dsh-toolgate 在回合结束时写）。
 */

import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

export const name = 'dsh-handin-bubble'

export const inject = ['webServer']

const 账本 = join(homedir(), 'Documents', 'deepseek-harness', 'default-workspace', 'body', 'renwu', '_催交.json')

export function apply(ctx, config = {}) {
  const route = (路径, handler) =>
    ctx.effect(() =>
      ctx.webServer.register({
        kind: 'exact',
        path: 路径,
        handler: async (req, res) => {
          try {
            await handler(req, res)
          } catch (e) {
            res.statusCode = 500
            res.setHeader('content-type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: false, 说: String((e && e.message) || e) }))
          }
        },
      }),
    )

  route('/dsh-handin/state', async (req, res) => {
    let 数据 = {}
    try {
      if (existsSync(账本)) 数据 = JSON.parse(readFileSync(账本, 'utf8'))
    } catch (e) {
      数据 = {}
    }
    const 欠 = Object.entries(数据)
      .filter(([, v]) => (v && v.次数) > 0)
      .map(([会话, v]) => ({
        会话,
        次数: v.次数 || 0,
        最近: v.最近 || '',
        调用数: v.调用数 || 0,
      }))
      .sort((a, b) => b.次数 - a.次数)
    res.statusCode = 200
    res.setHeader('content-type', 'application/json; charset=utf-8')
    res.end(JSON.stringify({ ok: true, 欠 }))
  })
}
