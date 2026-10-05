import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const NOW = Date.parse('2026-10-05T08:00:00-04:00')
const at = (minutes: number) => new Date(NOW + minutes * 60000).toISOString()

// Simplified stop lists, each in travel order for its direction.
const EAST = ['place-clmnl', 'place-tapst', 'place-wascm', 'place-cool', 'place-smary', 'place-kencl', 'place-gover']
const WEST = [...EAST].reverse()

const stops = (ids: string[]) => ({
  data: ids.map(id => ({ id, type: 'stop', attributes: { name: id.replace('place-', '') } })),
})

const ROUTES: Record<string, unknown> = {
  '/routes/Green-C': {
    data: { id: 'Green-C', type: 'route', attributes: { direction_destinations: ['Cleveland Circle', 'Government Center'] } },
  },
  '/stops?filter%5Broute%5D=Green-C&filter%5Bdirection_id%5D=1': stops(EAST),
  '/stops?filter%5Broute%5D=Green-C&filter%5Bdirection_id%5D=0': stops(WEST),
  '/vehicles?filter%5Broute%5D=Green-C&include=stop': {
    data: [
      // eastbound, stopped at Cleveland Circle: 2 stops before Washington Square
      { id: 'v1', type: 'vehicle', attributes: { current_status: 'STOPPED_AT' }, relationships: { stop: { data: { id: '70237' } } } },
      // westbound, heading into Kenmore: 1 stop before St. Mary's
      { id: 'v2', type: 'vehicle', attributes: { current_status: 'IN_TRANSIT_TO' }, relationships: { stop: { data: { id: '71151' } } } },
    ],
    included: [
      { id: '70237', type: 'stop', attributes: {}, relationships: { parent_station: { data: { id: 'place-clmnl' } } } },
      { id: '71151', type: 'stop', attributes: {}, relationships: { parent_station: { data: { id: 'place-kencl' } } } },
    ],
  },
  '/predictions?filter%5Bstop%5D=place-wascm&filter%5Broute%5D=Green-C&filter%5Bdirection_id%5D=1': {
    data: [
      { id: 'p2', type: 'prediction', attributes: { arrival_time: at(11), status: null }, relationships: { vehicle: { data: null } } },
      { id: 'p1', type: 'prediction', attributes: { arrival_time: at(4), status: null }, relationships: { vehicle: { data: { id: 'v1' } } } },
      { id: 'p0', type: 'prediction', attributes: { arrival_time: at(-2), status: null }, relationships: { vehicle: { data: null } } },
    ],
  },
  '/predictions?filter%5Bstop%5D=place-smary&filter%5Broute%5D=Green-C&filter%5Bdirection_id%5D=0': {
    data: [
      { id: 'p3', type: 'prediction', attributes: { arrival_time: null, departure_time: at(2), status: 'Approaching' }, relationships: { vehicle: { data: { id: 'v2' } } } },
    ],
  },
}

type Seen = { keys: (string | undefined)[]; statuses: (string | undefined)[]; toasts: string[]; notified: string[] }

function fakeMbta(on: On, seen: Seen, status = 200) {
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('ui.status', ($, e) => {
    seen.statuses.push(e.text)
    return { value: undefined }
  })
  on('ui.toast', ($, e) => {
    seen.toasts.push(e.text)
    return { value: undefined }
  })
  on('process.run', ($, e) => {
    seen.notified.push(e.argv.join(' '))
    return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('http.fetch', ($, e) => {
    const path = e.url.replace('https://api-v3.mbta.com', '')
    seen.keys.push(e.init?.headers?.['x-api-key'])
    const body = ROUTES[path]
    if (status !== 200) return { value: { status, ok: false, headers: {}, text: '' } }
    if (body === undefined) return { value: { status: 404, ok: false, headers: {}, text: `no fake for ${path}` } }
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify(body) } }
  })
}

const START = { cwd: '/', surface: 'terminal', isInteractive: true } as const
const RUN = {
  command: 'greenline',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: false, columns: 120 },
} as const

test('status line shows both stops with stops-away', { options: { api_key: 'secret' } }, async ($, on) => {
  const clock = mock.clock(on, { now: NOW })
  const seen: Seen = { keys: [], statuses: [], toasts: [], notified: [] }
  fakeMbta(on, seen)

  await $.session.start(START)
  await clock.settle()

  expect(seen.statuses.at(-1)).toBe("🚋 Wash Sq → Gov Ctr 4m (2 stops), 11m · St Mary's → Clev Cir 2m (1 stop)")
  expect(seen.keys.every(k => k === 'secret')).toBe(true)

  // re-polls vehicles + both stops every 30s; the route layout is cached
  const before = seen.keys.length
  await clock.advance(30_000)
  expect(seen.keys.length - before).toBe(3)

  const out = await $.command.run(RUN)
  expect(out.text).toContain('4 min · 2 stops away · at clmnl')
  expect(out.text).toContain('2 min · 1 stop away · → kencl · Approaching')
})

test('falls back to MBTA_API_KEY and reports API errors', async ($, on) => {
  mock.clock(on, { now: NOW })
  mock.env(on, { MBTA_API_KEY: 'from-env' })
  const seen: Seen = { keys: [], statuses: [], toasts: [], notified: [] }
  fakeMbta(on, seen, 403)

  await $.session.start(START)
  const out = await $.command.run(RUN)
  expect(out.text).toBe('Green Line: MBTA API 403 (check api_key)')
  expect(seen.keys[0]).toBe('from-env')
})

test('alerts once per train when it is 5 minutes out', async ($, on) => {
  const clock = mock.clock(on, { now: NOW })
  mock.env(on, {})
  const seen: Seen = { keys: [], statuses: [], toasts: [], notified: [] }
  fakeMbta(on, seen)

  // at start: Washington Sq's 4-minute train and St. Mary's 2-minute train are already inside 5
  await $.session.start(START)
  await clock.settle()
  expect(seen.toasts).toEqual([
    '🚋 Wash Sq → Gov Ctr: train in 4 min (2 stops away)',
    "🚋 St Mary's → Clev Cir: train in 2 min (1 stop away)",
  ])
  expect(seen.notified[0]).toBe(
    'osascript -e display notification "Wash Sq → Gov Ctr: train in 4 min (2 stops away)" with title "Green Line" sound name "Glass"',
  )

  // the same trains don't alert again
  await clock.advance(30_000)
  expect(seen.toasts.length).toBe(2)

  // six minutes in, the 11-minute train is 5 out: one new alert
  await clock.advance(5 * 60_000 + 30_000)
  expect(seen.toasts.slice(2)).toEqual(['🚋 Wash Sq → Gov Ctr: train in 5 min'])
  expect(seen.notified.length).toBe(3)
})

test('desktop_notify off keeps alerts inside Claude Code', { options: { desktop_notify: false } }, async ($, on) => {
  const clock = mock.clock(on, { now: NOW })
  mock.env(on, {})
  const seen: Seen = { keys: [], statuses: [], toasts: [], notified: [] }
  fakeMbta(on, seen)
  await $.session.start(START)
  await clock.settle()
  expect(seen.toasts.length).toBe(2)
  expect(seen.notified).toEqual([])
})
