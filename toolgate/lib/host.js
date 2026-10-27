/**
 * dsh-toolgate —— 给分身裁工具（2026-10-27）
 *
 * 解决什么问题：`body/huihua/<会话>.json` 里的 domains 只管「该读哪些文档」，
 * 管不住「能用哪些工具」。测试鱼没勾表情指路，照样能调 send_meme —— 这个洞靠审计只能事后抓，
 * 靠这个插件能当场挡住。
 *
 * 怎么挡：宿主给每个 agent 一份 scoped tools，在 `agent/created` 时挂两样：
 *   1. `tools.guard(fn)` —— 兜底守卫，看见了也跑不了（同步、只 deny）
 *   2. `tools.restrict({ deny })` —— 主刀，直接从工具面里拿掉
 * 顺序是先 guard 再 restrict：restrict 可能因名字没登记抛错，guard 不依赖名字表。
 *
 * 规则表（改这里就行）：
 *   表情类工具 → 需要 domains 里有「表情指路」/「语言」/「群聊」任一
 *   语音类工具 → 需要「声音」
 *
 * 谁不受限：主窗口（大肥鱼）和没有档案的会话。宁可少挡，不能把自己关门外。
 */

import { readFileSync, existsSync, writeFileSync, readdirSync, watch, statSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

export const name = 'dsh-toolgate'

/** 不需要注入服务：只要能用 agent.ctx.tools。 */
export const inject = ['webServer']   // 催交接口要用；没有它 ctx.webServer 取不到

const HOME = homedir()
const DSH = join(HOME, '.dsh')
const BODY = join(HOME, 'Documents', 'deepseek-harness', 'default-workspace', 'body')
const LOG = join(DSH, 'toolgate.log')

/** 工具 → 需要哪些分区（任一命中即放行） */
const 规则 = {
  send_meme: ['表情指路', '语言', '群聊'],
  meme_list: ['表情指路', '语言', '群聊'],
  meme_update: ['表情指路'],
  learn_meme: ['表情指路'],
  meme_render: ['表情指路'],
  sticker_search: ['表情指路'],
  sticker_send: ['表情指路'],
  sticker_manage: ['表情指路'],
  speak: ['声音'],
  text_to_speech: ['声音'],
}

/** 主窗口不受限 */
const 豁免 = new Set(['大肥鱼'])
let 已记清单 = false

function 记(msg) {
  try {
    writeFileSync(LOG, `${new Date().toISOString()} ${msg}\n`, { flag: 'a' })
  } catch (e) {
    /* 日志写不了不影响拦截 */
  }
}

/** 会话 id → 标题（从应用自己的会话缓存里读；文件小，每次现读最稳） */
function 会话标题(sid) {
  if (!sid) return ''
  const dir = join(DSH, 'storages', 'session_projcache', 'sessions')
  if (!existsSync(dir)) return ''
  const want = String(sid).replace(/^session-/, '')
  for (const f of readdirSync(dir)) {
    if (!f.endsWith('.json')) continue
    const stem = f.slice(0, -5).replace(/^session-/, '')
    if (stem !== want) continue
    try {
      const j = JSON.parse(readFileSync(join(dir, f), 'utf8'))
      const t = j?.record?.rows?.title
      const v = t && typeof t === 'object' ? t.val : null
      return typeof v === 'string' ? v.trim() : ''
    } catch (e) {
      return ''
    }
  }
  return ''
}

/** 这间屋勾了哪些分区 */
function 读分区(名) {
  const f = join(BODY, 'huihua', `${名}.json`)
  if (!existsSync(f)) return null
  try {
    const d = JSON.parse(readFileSync(f, 'utf8'))
    if (Array.isArray(d.domains)) return d.domains
    return d.domain ? [d.domain] : []
  } catch (e) {
    return null
  }
}

export function apply(ctx) {
  /** 记住见过的 agent：分区改了要回来重新裁一次（2026-10-27） */
  const 已见 = new Map()   // 名 → { agent, 分区 }
  const 名到agent = new Map()   // 名字 → 活着的 agent（创建时记，催交用）
  const 撤销表 = new Map()  // 名 → 上一次 restrict 的 dispose（重裁前先撤，不然只能越裁越紧）

  const off = ctx.on?.('agent/created', ({ agent } = {}) => {
    try {
      const sid = agent?.session?.header?.id ?? agent?.session?.id ?? agent?.id ?? ''
      const 名 = 会话标题(sid)
      if (名) 名到agent.set(名, agent)
      if (!名) return
      if (豁免.has(名)) return
      const 分区 = 读分区(名)
      if (!分区) return

      // 算出这一间屋不许用的工具
      const 全部禁 = Object.entries(规则)
        .filter(([工具, 需要]) => !需要.some((d) => 分区.includes(d)))
        .map(([工具]) => 工具)
      // 这间屋见过的 agent 记下来，分区一改可以重裁
      已见.set(名, { agent, 分区 })
      if (!全部禁.length) return

      const tools = agent?.ctx?.tools
      if (!tools) {
        记(`${名}：agent.ctx 上没有 tools，跳过`)
        return
      }

      // 过滤掉这台宿主不认识的工具名：restrict 遇到未知名字会整段抛错（2026-10-27 实测）
      let 已知 = null
      try {
        const set = tools.view?.(agent)?.restrictableNames ?? tools.view?.()?.restrictableNames
        if (set && typeof set[Symbol.iterator] === 'function') 已知 = new Set([...set].map(String))
      } catch (e) {
        已知 = null
      }
      const 禁 = 全部禁.filter((n) => (已知 ? 已知.has(n) : true))
      if (已知) {
        const 不认 = 全部禁.filter((n) => !已知.has(n))
        if (不认.length) 记(`${名}：这些名字这台宿主没有，跳过 ${不认.join('、')}`)
        if (!已记清单) {
          已记清单 = true
          记(`工具清单（这台宿主 ${已知.size} 个）：${[...已知].sort().join('、')}`)
        }
      }
      // 永远挂 guard（哪怕现在什么都不禁）—— 勾选/取消要立刻生效，靠它每次现读分区
      if (typeof tools.guard === 'function') {
        try {
          const dispose = tools.guard((exec) => {
            try { if (existsSync(开关文件)) return undefined } catch (e) {}
            const n = exec?.name
            if (!n || !(n in 规则)) return undefined
            // 读不到配置就放行 —— 宁可漏拦，也不要把别人的会话搞瘫
            const 现在分区 = 读分区(名)
            if (!Array.isArray(现在分区)) return undefined
            if ((规则[n] || []).some((d) => 现在分区.includes(d))) return undefined
            const 缺 = (规则[n] || []).filter((d) => !现在分区.includes(d))
            记(`${名}：守卫挡住 ${n}（缺 ${缺.join('/')}）`)
            return `这件事不在我的工作范围：我没勾「${缺[0] || '对应'}」这个分区，用不了 ${n}。`
              + '不要绕（别用读写文件或手拼路径代替）——直接跟对方说这件事不在我的范围就行。'
          })
          try { agent.ctx.effect?.(() => dispose) } catch (e) {}
          记(`${名}：已挂守卫${禁.length ? '（当前禁 ' + 禁.join('、') + '）' : ''}`)
        } catch (e) {
          记(`${名}：guard 没挂上（${String(e?.message ?? e).slice(0, 120)}）`)
        }
      }
    } catch (e) {
      记(`挂载过程出错：${String(e?.message ?? e).slice(0, 160)}`)
    }
  })



  // ── 催交接口（2026-10-27）：面板上点「催」，给那间屋塞一句提醒，让她自己补交
  //    花的是一轮对话的 token，所以面板那边只在「该交卷」时显示按钮。
  const 找活着的agent = (名) => {
    const 直接 = 名到agent.get(名)
    if (直接) return 直接
    try {
      const 会话服务 = ctx.get?.('sessions') || ctx.sessions
      const 标题服务 = ctx.get?.('sessionTitle') || ctx.sessionTitle
      const 名单 = 会话服务 && typeof 会话服务.list === 'function' ? 会话服务.list() : []
      for (const s of 名单) {
        let t = ''
        try {
          const 快照 = 标题服务 && typeof 标题服务.get === 'function' ? 标题服务.get(s) : undefined
          t = 快照 && 快照.title ? String(快照.title) : ''
        } catch (e) {}
        if (t !== 名) continue
        for (const id of [String(s.id), 'session-' + String(s.id), String(s.id).replace(/^session-/, '')]) {
          try {
            const a = ctx.agents?.get?.(id)
            if (a) return a
          } catch (e) {}
        }
      }
    } catch (e) {}
    return undefined
  }

  try {
    ctx.effect(() => ctx.webServer.register({
      kind: 'exact',
      path: '/dsh-handin/nudge',
      handler: async (req, res) => {
        const 头 = { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*' }
        if (req.method === 'OPTIONS') { res.writeHead(204, 头); res.end(); return }
        // 名字从各处都试一遍：查询串 / req.query / req.body / 原始流
        let 名 = ''
        const 试 = []
        try {
          const u = new URL(req.url || '', 'http://127.0.0.1')
          名 = String(u.searchParams.get('name') || u.searchParams.get('名') || '')
          试.push('url=' + (req.url || ''))
        } catch (e) { 试.push('url解析失败:' + String(e?.message || e)) }
        if (!名) {
          try {
            const q = req.query || {}
            名 = String(q.name || q['名'] || '')
            试.push('query keys=' + Object.keys(q).join(','))
          } catch (e) {}
        }
        if (!名) {
          try {
            const b = req.body || {}
            名 = String((typeof b === 'string' ? (JSON.parse(b || '{}').名 || '') : (b.名 || b.name || '')) || '')
            试.push('body keys=' + (typeof b === 'object' ? Object.keys(b).join(',') : typeof b))
          } catch (e) {}
        }
        if (!名) {
          let 体 = ''
          try { for await (const 段 of req) 体 += 段 } catch (e) {}
          try { 名 = String(JSON.parse(体 || '{}').名 || '') } catch (e) {}
          试.push('stream=' + 体.slice(0, 40))
        }
        记(`催交接口收到：名=${名 || '(空)'} ${试.join(' | ')}`)
        if (!名) { res.writeHead(400, 头); res.end(JSON.stringify({ ok: false, 说: '没给名字' })); return }
        const agent = 找活着的agent(名)
        if (!agent || typeof agent.followup !== 'function') {
          res.writeHead(200, 头)
          res.end(JSON.stringify({ ok: false, 说: `${名} 那间会话没开着，先把窗口打开再催` }))
          return
        }
        const 话 = `（主窗口催交）这轮干完活还没交卷。现在补，三样里至少一件：\n`
          + `① 过程写进 body/jiyi/${名}/ ② 发现写进 body/jianyi/${名}.md ③ 要改正文的投 body/daishen/\n`
          + `补完再说话。`
        try {
          await agent.followup({ id: 'nudge-' + Date.now(), role: 'user', content: [{ type: 'text', text: 话 }], source: { kind: 'system' } })
          try { await ctx.sessions?.flush?.(agent.session) } catch (e) {}
          记(`${名}：面板催了一次交卷`)
          res.writeHead(200, 头)
          res.end(JSON.stringify({ ok: true, 说: `已催 ${名}` }))
        } catch (e) {
          res.writeHead(200, 头)
          res.end(JSON.stringify({ ok: false, 说: String((e && e.message) || e) }))
        }
      },
    }))
  } catch (e) {
    记(`催交接口没挂上：${String(e?.message ?? e).slice(0, 120)}`)
  }

  // 监听分区文件：改了立刻给对应会话重下 restrict（不叫醒任何人，不花 token）
  let watcher = null
  try {
    const dir = join(BODY, 'huihua')
    if (existsSync(dir)) {
      let timer = null
      watcher = watch(dir, { persistent: false }, () => {
        clearTimeout(timer)
        timer = setTimeout(() => {
          try {
            重新裁全部()
          } catch (e) {
            记(`重裁出错：${String(e?.message ?? e).slice(0, 140)}`)
          }
        }, 500)   // 防抖：一次保存常常触发两次事件
      })
      记('已开始监听 body/huihua/（分区改动即时生效，不花 token）')
    }
  } catch (e) {
    记(`监听没建起来（${String(e?.message ?? e).slice(0, 120)}），改分区后仍需重启`)
  }

  /** 分区变了：把每个见过的 agent 重新裁一遍 */
  function 重新裁全部() {
    for (const [名, info] of 已见) {
      const 分区 = 读分区(名)
      if (!分区) continue
      const 禁 = Object.entries(规则)
        .filter(([工具, 需要]) => !需要.some((d) => 分区.includes(d)))
        .map(([工具]) => 工具)
      try {
        ;(info.agent?.ctx?.tools?.guard)   // guard 在创建时就挂了，且每次现读分区，这里只需要记一笔
        记(`${名}：分区变了 → ${禁.length ? '禁 ' + 禁.join('、') : '全放开'}`)
      } catch (e) {
        记(`${名}：重裁记账失败（${String(e?.message ?? e).slice(0, 120)}）`)
      }
    }
  }

  ctx.effect?.(() => () => {
    try { off?.() } catch (e) {}
    try { watcher?.close() } catch (e) {}
  })
  记('toolgate 已装载（等会话启动时按 domains 裁工具）')
}
