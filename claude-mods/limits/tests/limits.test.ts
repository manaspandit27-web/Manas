import { expect, mock, test } from 'claude-code/testing'

import { activeRate, parseHours, planWindow, statusText, type Sample } from '../hooks/burn'

const NOW = Date.parse('2026-10-04T10:00:00Z')
const H = 3_600_000
const FIVE = { kind: 'five_hour', percentUsed: 40, resetsAt: '2026-10-04T12:00:00Z' }
const WEEK = { kind: 'seven_day', percentUsed: 60, resetsAt: '2026-10-07T00:00:00Z' }

test('status line shows each window with its reset countdown', () => {
  expect(statusText([FIVE, WEEK], NOW)).toBe('5h 40% ↻2h00m · 7d 60% ↻2d14h')
  expect(statusText([], NOW)).toBeUndefined()
})

test('durations parse in hours', () => {
  expect(parseHours('12h')).toBe(12)
  expect(parseHours('90m fable')).toBe(1.5)
  expect(parseHours('2d')).toBe(48)
  expect(parseHours('fable')).toBeUndefined()
})

test('active rate ignores idle gaps', () => {
  // 10 points over 30 active minutes, then a 5-hour gap, then 5 more over 30 minutes
  const s: Sample[] = []
  for (let i = 0; i <= 10; i++) s.push({ t: NOW - 6 * H + i * 3 * 60_000, k: 'five_hour', p: 10 + i, r: 'a' })
  for (let i = 0; i <= 5; i++) s.push({ t: NOW - H + i * 6 * 60_000, k: 'five_hour', p: 30 + i, r: 'a' })
  const rate = activeRate(s, 'five_hour', NOW - 7 * 24 * H)
  expect(Math.round((rate ?? 0) * 100)).toBe(Math.round((15 / (70 / 60)) * 100))
})

test('planner: weekly window decides a 12h run', () => {
  expect(planWindow(WEEK, 2, 12, NOW).verdict).toBe('fits')
  expect(planWindow(WEEK, 3, 12, NOW).verdict).toBe('tight')
  expect(planWindow(WEEK, 5, 12, NOW).verdict).toBe('stalls')
  // 5h window at 30%/h: fills after 2h of the run's 12h, and every window after that
  const five = planWindow(FIVE, 30, 12, NOW)
  expect(five.verdict).toBe('stalls')
  expect(five.text).toContain('of every 5h')
  expect(planWindow(FIVE, 15, 12, NOW).verdict).toBe('fits')
  expect(planWindow(FIVE, undefined, 12, NOW).verdict).toBe('unknown')
})

test('/burn reports limits and plans a run', async ($, on) => {
  mock.clock(on, { now: NOW })
  const samples: Sample[] = []
  for (let i = 0; i <= 20; i++) {
    samples.push({ t: NOW - 2 * H + i * 3 * 60_000, k: 'five_hour', p: 20 + i, r: FIVE.resetsAt })
    samples.push({ t: NOW - 2 * H + i * 3 * 60_000, k: 'seven_day', p: 58 + i / 10, r: WEEK.resetsAt })
  }
  mock.store(on, { samples })
  on('session.usage', () => ({ value: { startedAt: NOW - H, context: { window: 200_000 }, rateLimits: [FIVE, WEEK] } }))
  const shown: (string | undefined)[] = []
  on('ui.status', (_$, e) => {
    shown.push(e.text)
    return { value: undefined }
  })
  const run = await $.command.run({
    command: 'burn',
    args: '12h',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: false, columns: 100 },
  })
  expect(run.text).toContain('5h    40%')
  expect(run.text).toContain('A 12h00m run')
  expect(run.text).toContain('7d:')
  expect(shown.at(-1)).toBe('5h 40% ↻2h00m · 7d 60% ↻2d14h')
})

test('crossing the warn threshold toasts once per window', async ($, on) => {
  mock.clock(on, { now: NOW })
  mock.store(on)
  const toasts: string[] = []
  on('ui.toast', (_$, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.status', () => ({ value: undefined }))
  const hot = { ...FIVE, percentUsed: 82 }
  const measure = { context: { window: 200_000 }, rateLimits: [hot, WEEK], changed: ['rateLimits'] as const }
  on('session.measure', (_$, e) => ({ changed: [...e.changed] }))
  await $.session.measure({ ...measure, changed: ['rateLimits'] })
  await $.session.measure({ ...measure, rateLimits: [{ ...hot, percentUsed: 84 }, WEEK], changed: ['rateLimits'] })
  expect(toasts).toEqual(['5h limit at 82%, resets in 2h00m'])
})
