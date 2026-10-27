/**
 * dsh-handin-bubble —— 谁没交卷，直接挂在 DSH 界面里（2026-10-27）
 *
 * 浏览器半端：往 shell.overlay 插一个小气泡，读宿主那边的 /dsh-handin/state，
 * 每 10 秒刷新一次。只读文件，不花 token。
 *
 * 约定照 dsh-nekowhale-stickers 的写法：__ModuleLoader__.load + module.exports.{name,inject,apply}。
 * 客户端插件**绝不能抛** —— 一抛整个界面会白屏。
 */
window.__ModuleLoader__.load({
  id: 'dsh-handin-bubble',
  factory: (require) => {
    const module = { exports: {} }
    const React = require('react')
    const h = React.createElement

    const API = '/dsh-handin/state'
    const 备用 = 'http://127.0.0.1:9888/api/debt'   // 宿主半端没装时，直接读面板服务

    const CSS = `
      .hdb-wrap { position: fixed; z-index: 40;
        font: 13px/1.5 "Microsoft YaHei", system-ui; color: #e8f1ff;
        background: rgba(19,33,53,.93); border: 1px solid #22354f; border-radius: 12px;
        padding: 8px 12px; min-width: 150px; box-shadow: 0 6px 20px rgba(0,0,0,.35);
        cursor: grab; user-select: none; }
      .hdb-wrap:active { cursor: grabbing; }
      .hdb-wrap.hdb-ok { border-color: #2c4a3a; }
      .hdb-head { font-size: 12px; color: #8fa8c8; margin-bottom: 4px; padding-right: 34px; }
      .hdb-open { position: absolute; right: 24px; top: 0; font-size: 12px; color: #6eaaff;
        cursor: pointer; padding: 4px 6px; border-radius: 6px; }
      .hdb-open:hover { background: rgba(110,170,255,.14); }
      .hdb-open:hover { text-decoration: underline; }
      .hdb-row { display: flex; justify-content: space-between; gap: 12px; }
      .hdb-name { color: #e8f1ff; }
      .hdb-n { color: #ff8a8a; font-weight: 700; }
      .hdb-nudge { font-size: 11px; color: #ffb0b0; border: 1px solid #4a3a52;
        background: #2a1f2e; border-radius: 5px; padding: 0 5px; margin-left: 6px;
        cursor: pointer; }
      .hdb-nudge:hover { background: #3a2a40; }
      .hdb-nudge[disabled] { color: #6c7a90; border-color: #2c3a4c; background: transparent; cursor: default; }
      .hdb-more { font-size: 11px; color: #8fa8c8; margin-top: 2px; }
      .hdb-close { position: absolute; right: 2px; top: 0; font-size: 16px; line-height: 1;
        color: #8fa8c8; cursor: pointer; padding: 4px 8px; border-radius: 6px; }
      .hdb-close:hover { background: rgba(255,255,255,.08); }
      .hdb-close:hover { color: #e8f1ff; }
      .hdb-mini { position: fixed; z-index: 40; width: 40px; height: 40px; border-radius: 20px;
        background: rgba(19,33,53,.94); border: 1px solid #22354f; color: #e8f1ff;
        display: flex; align-items: center; justify-content: center; cursor: grab;
        font: 15px/1 "Microsoft YaHei", system-ui; box-shadow: 0 4px 14px rgba(0,0,0,.35);
        user-select: none; }
      .hdb-mini:active { cursor: grabbing; }
      .hdb-dot { position: absolute; right: -2px; top: -2px; width: 10px; height: 10px;
        border-radius: 5px; background: #ff4d4d; box-shadow: 0 0 6px rgba(255,77,77,.9); }
    `

    function Bubble() {
      const [数据, 设数据] = React.useState(null)
      const [收起, 设收起] = React.useState(false)
      const [已读, 设已读] = React.useState(() => {
        try { return Number(localStorage.getItem('dsh-handin-seen') || '0') || 0 } catch (e) { return 0 }
      })
      const [位, 设位] = React.useState(() => {
        try {
          const 存 = JSON.parse(localStorage.getItem('dsh-handin-pos') || 'null')
          if (存 && typeof 存.x === 'number') return 存
        } catch (e) {}
        const w = typeof window !== 'undefined' ? window.innerWidth : 1200
        const h = typeof window !== 'undefined' ? window.innerHeight : 800
        return { x: Math.max(12, w - 210), y: Math.max(12, h - 190) }
      })
      // 位置只在拖动结束时写一次 localStorage —— 所以重启应用、刷新页面都还在原处
      const 拖 = React.useRef(null)
      const [催中, 设催中] = React.useState('')

      const 催 = (名) => {
        if (催中) return
        if (!window.confirm(`催 ${名} 一句？这要花一轮 token（几百到一千多）`)) return
        设催中(名)
        // 名字走查询串：宿主那边读 request body 不可靠，走 url 最稳
        fetch('/dsh-handin/nudge?name=' + encodeURIComponent(名), { method: 'POST' })
          .then((r) => r.json())
          .then((d) => {
            设催中('')
            if (!d.ok) { try { window.alert(d.说 || '催不了') } catch (e) {} }
            else { try { window.setTimeout(() => location.reload(), 800) } catch (e) {} }
          })
          .catch(() => 设催中(''))
      }

      React.useEffect(() => {
        let 活 = true
        const 拉 = () => {
          fetch(API, { cache: 'no-store' })
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error('no route'))))
            .then((d) => { if (活) 设数据(d) })
            .catch(() => fetch(备用, { cache: 'no-store' })
              .then((r) => r.json())
              .then((d) => { if (活) 设数据(d) })
              .catch(() => {}))
        }
        拉()
        const t = setInterval(拉, 10000)
        return () => { 活 = false; clearInterval(t) }
      }, [])

      const 欠 = (数据 && 数据.欠) || []
      const 总 = 欠.reduce((a, b) => a + (b.次数 || 0), 0)
      const 有新的 = 总 > 已读

      const 开面板 = (e) => {
        if (e) e.stopPropagation()
        try { window.open('http://127.0.0.1:9888/', '_blank') } catch (err) {}
      }

      const 拖动逻辑 = (e) => {
        const cls = String((e.target && e.target.className) || '')
        if (cls.includes('hdb-close') || cls.includes('hdb-open')) return
        e.preventDefault()
        拖.current = { dx: e.clientX - 位.x, dy: e.clientY - 位.y, 动过: false }
        const 移动 = (ev) => {
          if (!拖.current) return
          拖.current.动过 = true
          const nx = Math.max(0, Math.min(window.innerWidth - 60, ev.clientX - 拖.current.dx))
          const ny = Math.max(0, Math.min(window.innerHeight - 40, ev.clientY - 拖.current.dy))
          设位({ x: nx, y: ny })
        }
        const 松手 = () => {
          const 动过 = 拖.current && 拖.current.动过
          拖.current = null
          window.removeEventListener('mousemove', 移动)
          window.removeEventListener('mouseup', 松手)
          设位((cur) => {
            try { localStorage.setItem('dsh-handin-pos', JSON.stringify(cur)) } catch (err) {}
            return cur
          })
          if (!动过 && 收起) {
            // 只有「圆点」单击才展开；展开态点正文什么都不做
            设已读(总)
            try { localStorage.setItem('dsh-handin-seen', String(总)) } catch (err) {}
            设收起(false)
          }
        }
        window.addEventListener('mousemove', 移动)
        window.addEventListener('mouseup', 松手)
      }

      const 样式 = { left: 位.x + 'px', top: 位.y + 'px' }

      // 收起态：以「−」的位置为中心缩成一个小圆点（展开也回到同一处）
      if (收起) {
        const 圆点样式 = { left: (位.x + 168) + 'px', top: (位.y + 2) + 'px' }
        return h('div', {
          className: 'hdb-mini' + (有新的 ? ' hdb-mini-new' : ''),
          style: 圆点样式,
          title: 总 ? `欠 ${总} 次（点开）` : '没欠账（点开）',
          onMouseDown: 拖动逻辑,
        },
          h('span', null, 总 ? String(总) : '卷'),
          有新的 ? h('span', { className: 'hdb-dot' }) : null,
        )
      }

      if (!欠.length) {
        return h('div', { className: 'hdb-wrap hdb-ok', style: 样式, title: '没有欠账（可以拖动）', onMouseDown: 拖动逻辑 },
          h('span', { className: 'hdb-open', title: '打开本体面板',
            onMouseDown: (e) => e.stopPropagation(), onClick: 开面板 }, '面板↗'),
          h('span', { className: 'hdb-close', title: '收起',
            onMouseDown: (e) => e.stopPropagation(), onClick: (e) => { e.stopPropagation(); 设收起(true) } }, '−'),
          h('div', { className: 'hdb-head' }, '交卷'),
          h('div', { className: 'hdb-name' }, '没欠账 ✓'))
      }

      const 显示 = 欠.slice(0, 4)
      return h('div', { className: 'hdb-wrap', style: 样式, title: '按住可以拖到别处', onMouseDown: 拖动逻辑 },
        h('span', { className: 'hdb-open', title: '打开本体面板',
          onMouseDown: (e) => e.stopPropagation(), onClick: 开面板 }, '面板↗'),
        h('span', { className: 'hdb-close', title: '收起成小圆点',
          onMouseDown: (e) => e.stopPropagation(), onClick: (e) => { e.stopPropagation(); 设收起(true) } }, '−'),
        h('div', { className: 'hdb-head' }, `交卷 · 欠 ${总} 次`),
        ...显示.map((x) => h('div', { className: 'hdb-row', key: x.会话 },
          h('span', { className: 'hdb-name' }, x.会话),
          h('span', null,
            h('span', { className: 'hdb-n' }, '×' + (x.次数 || 0)),
            h('span', {
              className: 'hdb-nudge',
              title: '给她塞一句提醒，让她自己补交卷（花一轮 token）',
              onMouseDown: (e) => e.stopPropagation(),
              onClick: (e) => { e.stopPropagation(); 催(x.会话) },
            }, 催中 === x.会话 ? '催了' : '催')))),
        欠.length > 4 ? h('div', { className: 'hdb-more' }, `……还有 ${欠.length - 4} 个`) : null,
      )
    }

    module.exports.name = 'handin-bubble-client'
    module.exports.inject = ['slots']
    module.exports.apply = function apply(ctx) {
      try {
        const css = document.createElement('style')
        css.setAttribute('data-plugin-css', 'dsh-handin-bubble')
        css.textContent = CSS
        document.head.appendChild(css)
        ctx.effect(() => () => css.remove(), 'dsh-handin-bubble: 样式')
      } catch (e) {
        /* 样式失败不影响功能 */
      }
      try {
        ctx.slots.inject('shell.overlay', () => ctx.slots.register(
          { name: 'shell.overlay', id: 'handin-bubble', order: 120, label: '交卷' },
          Bubble,
        ))
      } catch (e) {
        try { console.warn('[handin-bubble] overlay disabled:', e) } catch (err) {}
      }
    }
    return module.exports
  },
})
