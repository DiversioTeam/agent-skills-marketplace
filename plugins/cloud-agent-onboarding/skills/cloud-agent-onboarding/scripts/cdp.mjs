#!/usr/bin/env node
// Drive a debug-port Chrome that the user has signed in to, one small action per call.
// Raw Chrome DevTools Protocol over WebSocket: no dependencies (Node 22+ has WebSocket).
// Playwright's connectOverCDP hung on some Chrome versions, so this avoids it.
//
//   CDP_PORT=9333 TAB=claude.ai/code node cdp.mjs <action> [args]
//   CDP_PORT: the Chrome debug port (default 9222). TAB: part of the tab URL to act on (default claude.ai).
//
//   tabs                          list page tabs
//   goto <url>                    navigate the matched tab
//   text [maxChars]               main column text (tail), or body text
//   shot [out.png]                screenshot the viewport (default cdp-shot-<time>.png in the current directory)
//   eval <js>                     evaluate an expression, print the JSON result
//   click-text <text>             click the smallest visible element whose text matches exactly
//   send <file>                   insert a prompt from a file into the claude.ai composer (no Enter)
//   enter                         press Enter
//   escape                        press Escape
//   idle [minutes]                wait until the TAB session stops working or needs input (default 15)
//   pick-env <Name>               select a claude.ai environment by name
//   mode <Auto|Accept edits|Plan> switch the session's permission mode
//   field-hash <Env> <marker>     open <Env>'s settings; print sha256 prefix + length of the textarea containing <marker>
//   fill-field <Env> <marker> <file>    replace that textarea with a file's contents, save, Escape on failure
//   fill-env-line <Env> <VAR>     read a value from stdin; write VAR=<value> into the variables box
//                                 only if VAR is present and empty; save; print only length + sha256 prefix
//
// Never closes the browser or tabs. Selectors are from claude.ai/code in October 2026 and drift;
// re-discover with: node cdp.mjs eval '[...document.querySelectorAll("[data-testid]")].map(e=>e.dataset.testid)'
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'

const PORT = process.env.CDP_PORT || '9222'
const MATCH = process.env.TAB || 'claude.ai'
const [action, ...args] = process.argv.slice(2)
// Stored fields lose their final newline, so hash without trailing newlines on both sides.
const sha = (s) => createHash('sha256').update(s.replace(/\n+$/, '')).digest('hex').slice(0, 12)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const js = (v) => JSON.stringify(v)

async function connect() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
  const pages = list.filter((t) => t.type === 'page')
  if (action === 'tabs') return { pages }
  const t = pages.find((x) => x.url.includes(MATCH))
  if (!t) throw new Error(`no tab whose URL contains ${js(MATCH)}; set TAB=`)
  const ws = new WebSocket(t.webSocketDebuggerUrl)
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j })
  let id = 0
  const pending = new Map()
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data)
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) }
  }
  const send = (method, params = {}) => new Promise((r) => {
    const i = ++id; pending.set(i, r); ws.send(js({ id: i, method, params }))
  })
  const evaluate = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
    if (r.result?.exceptionDetails) throw new Error(js(r.result.exceptionDetails).slice(0, 400))
    return r.result?.result?.value
  }
  const mouse = (type, p) => send('Input.dispatchMouseEvent', { type, x: p.x, y: p.y, button: 'left', clickCount: type === 'mouseMoved' ? 0 : 1 })
  const point = (sel) => evaluate(`(()=>{const e=${sel}; if(!e) return null; e.scrollIntoView({block:'center'}); const b=e.getBoundingClientRect(); return {x:b.x+Math.min(b.width/2,30),y:b.y+b.height/2}})()`)
  const hover = async (sel) => { const p = await point(sel); if (!p) throw new Error('not found: ' + sel); await mouse('mouseMoved', p); return p }
  const click = async (sel) => { const p = await hover(sel); await mouse('mousePressed', p); await mouse('mouseReleased', p) }
  const key = async (k, vk) => {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code: k, windowsVirtualKeyCode: vk })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code: k, windowsVirtualKeyCode: vk })
  }
  return { send, evaluate, hover, click, key, close: () => ws.close() }
}

const q = (s) => `document.querySelector(${js(s)})`
// Exact match: the last line of the row's label before ", environment settings" must equal the name,
// so "Product" never selects "Other Product".
const envRow = (name) => `[...document.querySelectorAll('[role=menuitemradio]')].find(e=>{const t=e.innerText||e.textContent||'';
  const i=t.indexOf(', environment settings'); if(i<0) return false;
  return t.slice(0,i).split('\\n').pop().trim()===${js(name)}})`

async function openEnvMenu(c, name) {
  if (!(await c.evaluate(`!!${q('[data-testid="env-picker-more"]')}`))) {
    await c.click(q('[data-testid="environment-bar-trigger"]')); await sleep(800)
  }
  for (let i = 0; i < 10 && !(await c.evaluate(`!!(${envRow(name)})`)); i++) {
    await c.hover(q('[data-testid="env-picker-more"]')); await sleep(700)
  }
  if (!(await c.evaluate(`!!(${envRow(name)})`))) throw new Error(`environment ${js(name)} not in the picker`)
  await c.hover(envRow(name)); await sleep(300)
}

// Opens the named environment's settings dialog and checks it is the right one.
async function openEnvSettings(c, name) {
  await openEnvMenu(c, name)
  await c.click(`(${envRow(name)})?.querySelector('button')`); await sleep(1500)
  const ok = await c.evaluate(`(()=>{const d=document.querySelector('[role=dialog]'); if(!d) return 'no dialog';
    return [...d.querySelectorAll('input')].some(i=>i.value===${js(name)}) ? 'ok' : 'env name mismatch'})()`)
  if (ok !== 'ok') { await c.key('Escape', 27); throw new Error(ok) }
}

const setAndSave = (findTa, newValue) => `(()=>{const d=document.querySelector('[role=dialog]'); const ta=(${findTa}); if(!ta) return 'textarea not found';
  const v=(${newValue}); if(typeof v!=='string') return v?.refuse || 'no new value';
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta, v);
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  const save=[...d.querySelectorAll('button')].find(b=>/^Save/.test(b.innerText.trim())); if(!save) return 'no save button';
  save.click(); return 'saved'})()`
const taWith = (marker) => `[...d.querySelectorAll('textarea')].find(t=>t.value.includes(${js(marker)}))`

async function readStdin() { let s = ''; for await (const ch of process.stdin) s += ch; return s.trim() }

const c = await connect()
try {
  switch (action) {
    case 'tabs':
      for (const p of c.pages) console.log(p.url, '|', p.title)
      break
    case 'goto':
      await c.send('Page.navigate', { url: args[0] }); await sleep(3000)
      console.log(await c.evaluate('location.href'))
      break
    case 'text': {
      const t = await c.evaluate(`(document.querySelector('[data-testid=epitaxy-virtual-transcript]')||document.querySelector('main')||document.body).innerText`)
      console.log(t.slice(-Number(args[0] || 4000)))
      break
    }
    case 'shot': {
      const r = await c.send('Page.captureScreenshot', { format: 'png' })
      const out = args[0] || `cdp-shot-${new Date().toISOString().replace(/[:.]/g, '-')}.png`
      writeFileSync(out, Buffer.from(r.result.data, 'base64')); console.log(out)
      break
    }
    case 'eval':
      console.log(js(await c.evaluate(args[0]), null, 1))
      break
    case 'click-text':
      await c.click(`[...document.querySelectorAll('button,a,[role=menuitem],[role=option],span,div')].filter(e=>e.offsetParent&&e.innerText?.trim()===${js(args[0])}).pop()`)
      break
    case 'send': {
      const box = `${q('[data-testid=code-prompt-input]')}`
      const before = await c.evaluate(`(${box}?.innerText||'').trim()`)
      if (before) throw new Error('composer is not empty; refusing to append')
      await c.click(`document.querySelector('[data-testid=code-prompt-input] [contenteditable], [data-testid=code-prompt-input] textarea, [data-testid=code-prompt-input]')`)
      await sleep(300)
      await c.send('Input.insertText', { text: readFileSync(args[0], 'utf8').trim() }); await sleep(800)
      console.log(js((await c.evaluate(`${box}.innerText`)).slice(0, 120)))
      break
    }
    case 'enter': await c.key('Enter', 13); break
    case 'escape': await c.key('Escape', 27); break
    case 'idle': {
      const minutes = Number(args[0] || 15)
      if (!(minutes > 0)) throw new Error('idle takes minutes only; choose the tab with TAB=<part of its URL>')
      const end = Date.now() + minutes * 60000
      let s
      while (Date.now() < end) {
        s = await c.evaluate(`(()=>{const t=document.querySelector('[data-testid=epitaxy-virtual-transcript]')?.innerText||'';
          return {needsInput: t.includes('Needs your input') || !!document.querySelector('[role=radiogroup]'),
                  busy: !!document.querySelector('button[aria-label*=Stop i]') || /Running…|Publishing…|Setting up/.test(t.slice(-400))}})()`)
        if (s.needsInput || !s.busy) { await sleep(20000); const again = await c.evaluate(`!!document.querySelector('button[aria-label*=Stop i]')`); if (!again) break }
        await sleep(10000)
      }
      console.log(js(s))
      break
    }
    case 'pick-env': {
      await openEnvMenu(c, args[0])
      const p = await c.evaluate(`(()=>{const b=(${envRow(args[0])}).getBoundingClientRect(); return {x:b.x+30,y:b.y+b.height/2}})()`)
      await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: p.x, y: p.y, button: 'left', clickCount: 1 })
      await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: p.x, y: p.y, button: 'left', clickCount: 1 })
      await sleep(1500)
      const row = await c.evaluate(`document.querySelector('[data-testid=environment-bar-row]')?.innerText||''`)
      console.log(js(row))
      if (!row.split(/[\n·|]/).map((s) => s.trim()).includes(args[0])) throw new Error(`selected environment is not ${js(args[0])}`)
      break
    }
    case 'mode': {
      await c.click(`[...document.querySelectorAll('button')].find(b=>/^(Auto|Accept edits|Plan)$/.test(b.innerText.trim()))`); await sleep(600)
      await c.click(`[...document.querySelectorAll('[role=menuitem],[role=menuitemradio],[role=option]')].find(e=>e.innerText.trim().startsWith(${js(args[0])}))`)
      await sleep(600); console.log('mode requested:', args[0])
      break
    }
    case 'field-hash': {
      await openEnvSettings(c, args[0])
      const v = await c.evaluate(`(()=>{const d=document.querySelector('[role=dialog]'); const ta=${taWith(args[1])}; return ta?ta.value:null})()`)
      console.log(args[0], v == null ? 'not found' : `sha256:${sha(v)} len ${v.length}`)
      await c.key('Escape', 27)
      break
    }
    case 'fill-field': {
      const content = readFileSync(args[2], 'utf8')
      await openEnvSettings(c, args[0])
      const r = await c.evaluate(setAndSave(taWith(args[1]), js(content)))
      console.log(args[0], r, `local sha256:${sha(content)}`)
      await sleep(1500); if (r !== 'saved') { await c.key('Escape', 27); throw new Error(`not saved: ${r}`) }
      break
    }
    case 'fill-env-line': {
      const [envName, name] = args
      const value = await readStdin()
      if (value.length < 8 || /\s/.test(value)) throw new Error('value shape unexpected; aborting')
      console.log('value', `sha256:${sha(value)} len ${value.length}`)
      await openEnvSettings(c, envName)
      const findTa = `[...d.querySelectorAll('textarea')].find(t=>t.value.split('\\n').some(l=>l.startsWith(${js(name + '=')})))`
      const newValue = `(()=>{const lines=ta.value.split('\\n'); const i=lines.findIndex(l=>l.startsWith(${js(name + '=')}));
        if(lines[i].slice(${name.length + 1}).trim()) return {refuse: 'already filled; refusing to overwrite'};
        lines[i]=${js(name + '=' + value)}; return lines.join('\\n')})()`
      const r = await c.evaluate(setAndSave(findTa, newValue))
      console.log(envName, r)
      await sleep(1500); if (r !== 'saved') { await c.key('Escape', 27); throw new Error(`not saved: ${r}`) }
      break
    }
    default:
      console.log('unknown action; see the header of this file'); process.exitCode = 2
  }
} catch (e) {
  console.log('STEP ERROR:', String(e.message || e).split('\n')[0]); process.exitCode = 1
} finally {
  c.close?.()
}
