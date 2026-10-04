import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

import {
  activeRate,
  fmtDur,
  label,
  lastHourRate,
  modelRate,
  parseHours,
  planWindow,
  statusText,
  untilReset,
  worst,
  type ModelStats,
  type Sample,
  type Window,
} from './burn'

type $ = EngineInterface

const DAY = 86_400_000
const MAX_SAMPLES = 4000

const copy = (w: SessionRateLimit): Window => ({
  kind: w.kind,
  percentUsed: w.percentUsed,
  ...(w.resetsAt === undefined ? {} : { resetsAt: w.resetsAt }),
})

async function samplesOf($: $): Promise<Sample[]> {
  const v = await $.store.get('samples')
  return Array.isArray(v) ? (v as Sample[]) : []
}

async function modelsOf($: $): Promise<ModelStats> {
  const v = await $.store.get('models')
  return v !== null && typeof v === 'object' ? (v as ModelStats) : {}
}

let warnAt = 80
let wrapUpAt = 95
let windows: Window[] = []
let turn: { id: string; model: string; at: Record<string, Window> } | undefined

async function refresh($: $) {
  $.ui.status(statusText(windows, await $.clock.now()))
}

async function record($: $, now: number) {
  const fresh = windows.map(w => ({ t: now, k: w.kind, p: w.percentUsed, r: w.resetsAt ?? '' }))
  const kept = (await samplesOf($)).filter(s => s.t > now - 8 * DAY)
  await $.store.set('samples', [...kept, ...fresh].slice(-MAX_SAMPLES))
}

async function wrapUp($: $, w: Window, now: number) {
  const reset = untilReset(w, now)
  const when = reset === undefined ? '' : ` (resets in ${fmtDur(reset)})`
  $.ui.toast(`${label(w.kind)} limit at ${Math.round(w.percentUsed)}%${when}: wrapping up`, { timeoutMs: 10_000 })
  if (turn !== undefined) {
    await $.session.append({
      message: {
        type: 'user',
        content: [
          {
            type: 'text',
            text: `[limits mod] The ${label(w.kind)} usage limit is at ${Math.round(w.percentUsed)}%${when}. Finish the step you are on, leave the work in a clean, resumable state (commit or note anything half-done), then stop and say where things stand. A handoff note will be written automatically.`,
          },
        ],
      },
    })
  }
  // Queued until the session is idle; the handoff mod answers it when loaded.
  $.clock.after(1000, () => {
    void (async () => {
      const has = (await $.command.list()).some(c => c.name === 'handoff')
      if (has) await $.command.run({ command: 'handoff', args: 'limit' })
    })().catch(() => undefined)
  })
}

async function alert($: $, now: number) {
  const stored = await $.store.get('alerts')
  const alerts: Record<string, number> =
    stored !== null && typeof stored === 'object' ? { ...(stored as Record<string, number>) } : {}
  for (const key of Object.keys(alerts)) if ((alerts[key] ?? 0) < now) delete alerts[key]

  const thresholds = [wrapUpAt, warnAt].filter(t => t > 0).sort((a, b) => b - a)
  for (const w of windows) {
    const crossed = thresholds.filter(t => w.percentUsed >= t)
    const fresh = crossed.filter(t => alerts[`${w.kind}|${w.resetsAt ?? ''}|${t}`] === undefined)
    const expires = now + (untilReset(w, now) ?? 7 * DAY) + DAY
    for (const t of crossed) alerts[`${w.kind}|${w.resetsAt ?? ''}|${t}`] = expires
    const top = fresh[0]
    if (top === undefined) continue
    if (top === wrapUpAt) {
      await wrapUp($, w, now)
    } else {
      const reset = untilReset(w, now)
      $.ui.toast(
        `${label(w.kind)} limit at ${Math.round(w.percentUsed)}%${reset === undefined ? '' : `, resets in ${fmtDur(reset)}`}`,
        { timeoutMs: 8000 },
      )
    }
  }
  await $.store.set('alerts', alerts)
}

export const register: Register = (on, options) => {
  warnAt = Number(options.warnAt ?? 80)
  wrapUpAt = Number(options.wrapUpAt ?? 95)

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'burn',
      description: 'Rate limits, burn rate, and whether a run of a given length fits',
      argumentHint: '[12h|90m] [model]',
    })
    windows = (await $.session.usage()).rateLimits.map(copy)
    await refresh($)
    $.clock.every(60_000, () => void refresh($))
    return started
  })

  on('session.measure', async ($, e, next) => {
    const measured = await next(e)
    if (e.changed.includes('rateLimits')) {
      const now = await $.clock.now()
      windows = e.rateLimits.map(copy)
      await refresh($)
      await record($, now)
      await alert($, now)
    }
    return measured
  })

  on('turn.start', async ($, e, next) => {
    turn = {
      id: e.turnId,
      model: await $.session.model(),
      at: Object.fromEntries(windows.map(w => [w.kind, w])),
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    const started = turn
    if (started === undefined || started.id !== e.turnId || e.agentId !== undefined) return done
    turn = undefined
    const model = e.usage?.model ?? started.model
    const now = (await $.session.usage()).rateLimits.map(copy)
    const stats = await modelsOf($)
    const mine = { ...(stats[model] ?? {}) }
    for (const w of now) {
      const before = started.at[w.kind]
      if (before === undefined || before.resetsAt !== w.resetsAt) continue
      const was = mine[w.kind] ?? { p: 0, ms: 0, turns: 0 }
      mine[w.kind] = {
        p: was.p + Math.max(0, w.percentUsed - before.percentUsed),
        ms: was.ms + e.durationMs,
        turns: was.turns + 1,
      }
    }
    await $.store.set('models', { ...stats, [model]: mine })
    return done
  })

  on('command.run', { command: 'burn' }, async ($, e) => {
    const now = await $.clock.now()
    const usage = await $.session.usage()
    windows = usage.rateLimits.map(copy)
    await refresh($)
    if (windows.length === 0) {
      return {
        text: 'No rate-limit readings yet: they arrive with the first response, and only on a Claude subscription.',
      }
    }

    const samples = await samplesOf($)
    const stats = await modelsOf($)
    const lines: string[] = ['Limits']
    for (const w of windows) {
      const reset = untilReset(w, now)
      const at = reset === undefined ? '' : `  resets in ${fmtDur(reset)} (${new Date(now + reset).toLocaleString()})`
      lines.push(`  ${label(w.kind).padEnd(4)} ${String(Math.round(w.percentUsed)).padStart(3)}%${at}`)
    }

    const week = now - 7 * DAY
    const rates: Record<string, number | undefined> = {}
    lines.push('', 'Burn')
    for (const w of windows) {
      const active = activeRate(samples, w.kind, week)
      const hour = lastHourRate(samples, w, now)
      rates[w.kind] = active
      const a = active === undefined ? 'n/a' : `${active.toFixed(1)}%/active h (7d)`
      const h = hour === undefined ? 'n/a' : `${hour.toFixed(1)}%/h`
      lines.push(`  ${label(w.kind).padEnd(4)} ${a} · last hour ${h}`)
    }

    const models = Object.keys(stats)
    if (models.length > 0) {
      lines.push('', 'By model, while its turns ran (account-wide, so parallel sessions count too)')
      for (const m of models) {
        const parts = windows.map(w => {
          const r = modelRate(stats, m, w.kind)
          return `${label(w.kind)} ${r === undefined ? 'n/a' : `${r.toFixed(1)}%/h`}`
        })
        const turns = Math.max(0, ...Object.values(stats[m] ?? {}).map(s => s.turns))
        lines.push(`  ${m}: ${parts.join(' · ')} (${turns} turns)`)
      }
    }

    const hours = parseHours(e.args)
    if (hours !== undefined) {
      const rest = e.args.replace(/(\d+(?:\.\d+)?)\s*(d|h|m)\b/i, '').trim().toLowerCase()
      const model = rest === '' ? undefined : models.find(m => m.toLowerCase().includes(rest))
      const plan = windows.map(w =>
        planWindow(w, (model === undefined ? undefined : modelRate(stats, model, w.kind)) ?? rates[w.kind], hours, now),
      )
      const verdict = worst(plan)
      const head =
        verdict === 'fits'
          ? '✓ fits'
          : verdict === 'tight'
            ? '~ fits, but ends close to the limit'
            : verdict === 'stalls'
              ? '✗ hits a limit: it will stall unless it is shorter or cheaper'
              : '? not enough history to say yet'
      lines.push(
        '',
        `A ${fmtDur(hours * 3_600_000)} run${model === undefined ? '' : ` on ${model}`}: ${head}`,
        ...plan.map(p => `  ${p.text}`),
      )
      if (rest !== '' && model === undefined) lines.push(`  (no history for a model matching "${rest}"; used the overall rate)`)
    } else {
      lines.push('', 'Plan a run: /burn 12h, or /burn 3h fable for one model.')
    }
    return { text: lines.join('\n') }
  })
}
