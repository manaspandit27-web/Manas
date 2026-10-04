// Pure helpers for the limits mod: formatting, burn rates and the run planner.

export type Window = { kind: string; percentUsed: number; resetsAt?: string }
/** One reading of one window: time, kind, percent, the window's reset stamp. */
export type Sample = { t: number; k: string; p: number; r: string }
export type ModelStat = { p: number; ms: number; turns: number }
/** model -> window kind -> percent burned while that model's turns ran */
export type ModelStats = Record<string, Record<string, ModelStat>>

const HOUR = 3_600_000
const ACTIVE_GAP = 10 * 60_000
const PERIOD_HOURS: Record<string, number> = { five_hour: 5, seven_day: 168 }

export const label = (kind: string): string =>
  kind === 'five_hour' ? '5h' : kind === 'seven_day' ? '7d' : kind.replace(/_/g, ' ')

export function fmtDur(ms: number): string {
  if (!Number.isFinite(ms)) return '∞'
  const m = Math.max(0, Math.round(ms / 60_000))
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  const mm = m % 60
  if (d > 0) return `${d}d${h}h`
  if (h > 0) return `${h}h${String(mm).padStart(2, '0')}m`
  return `${mm}m`
}

export function untilReset(w: Window, now: number): number | undefined {
  if (w.resetsAt === undefined) return undefined
  const t = Date.parse(w.resetsAt)
  return Number.isNaN(t) ? undefined : Math.max(0, t - now)
}

export function statusText(ws: readonly Window[], now: number): string | undefined {
  if (ws.length === 0) return undefined
  return ws
    .map(w => {
      const u = untilReset(w, now)
      return `${label(w.kind)} ${Math.round(w.percentUsed)}%${u === undefined ? '' : ` ↻${fmtDur(u)}`}`
    })
    .join(' · ')
}

/** Readings closer than ACTIVE_GAP belong to one stretch of activity. */
function activeHours(samples: readonly Sample[]): number {
  const ts = samples.map(s => s.t).sort((a, b) => a - b)
  if (ts.length === 0) return 0
  let total = 0
  let start = ts[0]!
  let last = start
  for (const t of ts.slice(1)) {
    if (t - last > ACTIVE_GAP) {
      total += last - start + ACTIVE_GAP / 2
      start = t
    }
    last = t
  }
  total += last - start + ACTIVE_GAP / 2
  return total / HOUR
}

/**
 * Percent per hour of activity for one window kind since `since`: the rises
 * between close readings of the same window, over the time any window was
 * moving. A rise across a long gap (usage outside these sessions) is left out.
 * Undefined until there is enough history to say.
 */
export function activeRate(samples: readonly Sample[], kind: string, since: number): number | undefined {
  const recent = samples.filter(s => s.t >= since)
  const own = recent.filter(s => s.k === kind).sort((a, b) => a.t - b.t)
  let rise = 0
  for (let i = 1; i < own.length; i++) {
    const a = own[i - 1]!
    const b = own[i]!
    if (a.r === b.r && b.p > a.p && b.t - a.t <= ACTIVE_GAP) rise += b.p - a.p
  }
  const hours = activeHours(recent)
  return hours < 0.25 || rise === 0 ? undefined : rise / hours
}

/** Wall-clock percent per hour over the last hour, within the current window. */
export function lastHourRate(samples: readonly Sample[], w: Window, now: number): number | undefined {
  const own = samples
    .filter(s => s.k === w.kind && s.r === (w.resetsAt ?? '') && s.t >= now - HOUR)
    .sort((a, b) => a.t - b.t)
  const first = own[0]
  if (first === undefined) return undefined
  return Math.max(0, w.percentUsed - first.p) / Math.max((now - first.t) / HOUR, 0.25)
}

export function modelRate(stats: ModelStats, model: string, kind: string): number | undefined {
  const s = stats[model]?.[kind]
  return s === undefined || s.ms < 10 * 60_000 ? undefined : s.p / (s.ms / HOUR)
}

export type Verdict = 'fits' | 'tight' | 'stalls' | 'unknown'
export type PlanLine = { kind: string; verdict: Verdict; text: string }

/** Whether `hours` of work at `rate` %/h fits in window `w`, resets included. */
export function planWindow(w: Window, rate: number | undefined, hours: number, now: number): PlanLine {
  const name = label(w.kind)
  if (rate === undefined || rate <= 0) {
    return { kind: w.kind, verdict: 'unknown', text: `${name}: no burn history yet` }
  }
  const left = Math.max(0, 100 - w.percentUsed)
  const need = rate * hours
  const resetMs = untilReset(w, now)
  const resetH = resetMs === undefined ? undefined : resetMs / HOUR
  const period = PERIOD_HOURS[w.kind]
  const per = `${rate.toFixed(rate < 10 ? 1 : 0)}%/h`

  if (resetH === undefined || resetH >= hours) {
    if (need <= left) {
      const end = w.percentUsed + need
      return {
        kind: w.kind,
        verdict: end > 90 ? 'tight' : 'fits',
        text: `${name}: needs ~${Math.round(need)}% at ${per}, ${Math.round(left)}% left → ends near ${Math.round(end)}%`,
      }
    }
    return {
      kind: w.kind,
      verdict: 'stalls',
      text: `${name}: needs ~${Math.round(need)}% at ${per}, only ${Math.round(left)}% left → runs out after ~${fmtDur((left / rate) * HOUR)}${resetMs === undefined ? '' : `, resets in ${fmtDur(resetMs)}`}`,
    }
  }

  // The run outlasts this window's reset.
  const hitH = left / rate
  const stallNow = hitH < resetH ? resetH - hitH : 0
  const perPeriod = period === undefined ? 0 : rate * period
  const stallEach = period !== undefined && perPeriod > 100 ? period - 100 / rate : 0
  if (stallNow === 0 && stallEach === 0) {
    return { kind: w.kind, verdict: 'fits', text: `${name}: resets in ${fmtDur(resetH * HOUR)}; at ${per} it never fills` }
  }
  const parts: string[] = []
  if (stallNow > 0) parts.push(`fills in ~${fmtDur(hitH * HOUR)}, idle ~${fmtDur(stallNow * HOUR)} until its reset`)
  if (stallEach > 0) parts.push(`then idle ~${fmtDur(stallEach * HOUR)} of every ${period}h`)
  return { kind: w.kind, verdict: 'stalls', text: `${name}: at ${per} ${parts.join(', ')}` }
}

export function parseHours(args: string): number | undefined {
  const m = /(\d+(?:\.\d+)?)\s*(d|h|m)\b/i.exec(args)
  if (m === null) return undefined
  const n = Number(m[1])
  const unit = m[2]!.toLowerCase()
  return unit === 'd' ? n * 24 : unit === 'm' ? n / 60 : n
}

export function worst(lines: readonly PlanLine[]): Verdict {
  const order: Verdict[] = ['stalls', 'tight', 'unknown', 'fits']
  return order.find(v => lines.some(l => l.verdict === v)) ?? 'unknown'
}
