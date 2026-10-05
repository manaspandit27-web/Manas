// MBTA V3 API: the Green Line C branch, two stops, one direction each.
// Pure logic plus the requests it makes; register.ts wires it to Claude Code.

export const ROUTE = 'Green-C'
export const API = 'https://api-v3.mbta.com'

export type Watch = {
  /** Short label for the status line. */
  label: string
  /** Parent station id (`place-...`). */
  stop: string
  /** Matched against the route's direction_destinations to pick a direction. */
  towards: string
  /** Used if the route lookup fails: 0 = westbound, 1 = eastbound on Green-C. */
  fallbackDirection: 0 | 1
}

export const WATCHES: readonly Watch[] = [
  { label: 'Wash Sq → Gov Ctr', stop: 'place-wascm', towards: 'Government Center', fallbackDirection: 1 },
  { label: "St Mary's → Clev Cir", stop: 'place-smary', towards: 'Cleveland Circle', fallbackDirection: 0 },
]

export type Arrival = {
  /** The MBTA's prediction id: one per train per stop, stable while it approaches. */
  id: string
  minutes: number
  /** Stops between the train and the watched stop; undefined when the train isn't on the line yet. */
  stopsAway?: number
  /** Where the train is now, e.g. "at Coolidge Corner" or "→ Summit Avenue". */
  where?: string
  /** The MBTA's own status text when it gives one ("Boarding", "Approaching"). */
  status?: string
}

export type Board = { watch: Watch; arrivals: Arrival[] }

export type Fetch = (path: string, params: Record<string, string>) => Promise<unknown>

type Resource = {
  id: string
  type: string
  attributes: Record<string, unknown>
  relationships?: Record<string, { data: { id: string } | null } | undefined>
}
type Doc = { data: Resource | Resource[]; included?: Resource[] }

const rel = (r: Resource | undefined, name: string): string | undefined =>
  r?.relationships?.[name]?.data?.id ?? undefined

/** Route layout: direction per watch, and each direction's stops in travel order. */
export type Layout = { directions: number[]; order: Record<number, string[]>; names: Record<string, string> }

export async function loadLayout(fetch: Fetch): Promise<Layout> {
  let destinations: string[] = []
  try {
    const route = (await fetch(`/routes/${ROUTE}`, {})) as Doc
    destinations = ((route.data as Resource).attributes.direction_destinations as string[]) ?? []
  } catch {
    // fall back to the hardcoded directions below
  }
  const directions = WATCHES.map(w => {
    const i = destinations.findIndex(d => d.toLowerCase().includes(w.towards.toLowerCase()))
    return i >= 0 ? i : w.fallbackDirection
  })
  const order: Record<number, string[]> = {}
  const names: Record<string, string> = {}
  for (const dir of new Set(directions)) {
    const stops = (await fetch('/stops', { 'filter[route]': ROUTE, 'filter[direction_id]': String(dir) })) as Doc
    order[dir] = (stops.data as Resource[]).map(s => {
      names[s.id] = String(s.attributes.name)
      return s.id
    })
  }
  return { directions, order, names }
}

/** Where each vehicle on the route is: its parent station and its status there. */
export type Positions = Record<string, { station: string; status: string }>

export function positionsOf(doc: Doc): Positions {
  const parents: Record<string, string> = {}
  for (const s of doc.included ?? []) {
    if (s.type === 'stop') parents[s.id] = rel(s, 'parent_station') ?? s.id
  }
  const out: Positions = {}
  for (const v of doc.data as Resource[]) {
    const stop = rel(v, 'stop')
    if (stop === undefined) continue
    out[v.id] = { station: parents[stop] ?? stop, status: String(v.attributes.current_status ?? '') }
  }
  return out
}

export function arrivalsOf(
  doc: Doc,
  watch: Watch,
  stopsInOrder: string[],
  positions: Positions,
  names: Record<string, string>,
  now: number,
): Arrival[] {
  const target = stopsInOrder.indexOf(watch.stop)
  const out: Arrival[] = []
  for (const p of doc.data as Resource[]) {
    const time = (p.attributes.arrival_time ?? p.attributes.departure_time) as string | null
    if (!time) continue
    const minutes = Math.round((Date.parse(time) - now) / 60000)
    if (minutes < 0) continue
    const arrival: Arrival = { id: p.id, minutes }
    if (typeof p.attributes.status === 'string' && p.attributes.status) arrival.status = p.attributes.status
    const vehicle = rel(p, 'vehicle')
    const at = vehicle === undefined ? undefined : positions[vehicle]
    const here = at === undefined ? -1 : stopsInOrder.indexOf(at.station)
    if (at !== undefined && here >= 0 && target >= 0 && here <= target) {
      arrival.stopsAway = target - here
      const name = names[at.station] ?? at.station
      arrival.where = at.status === 'STOPPED_AT' ? `at ${name}` : `→ ${name}`
    }
    out.push(arrival)
  }
  return out.sort((a, b) => a.minutes - b.minutes)
}

export async function loadBoards(fetch: Fetch, layout: Layout, now: number): Promise<Board[]> {
  const positions = positionsOf((await fetch('/vehicles', { 'filter[route]': ROUTE, include: 'stop' })) as Doc)
  return Promise.all(
    WATCHES.map(async (watch, i) => {
      const dir = layout.directions[i] ?? watch.fallbackDirection
      const doc = (await fetch('/predictions', {
        'filter[stop]': watch.stop,
        'filter[route]': ROUTE,
        'filter[direction_id]': String(dir),
      })) as Doc
      return { watch, arrivals: arrivalsOf(doc, watch, layout.order[dir] ?? [], positions, layout.names, now) }
    }),
  )
}

const mins = (a: Arrival) => (a.minutes === 0 ? 'now' : `${a.minutes}m`)

function away(a: Arrival): string {
  if (a.stopsAway === undefined) return ''
  if (a.stopsAway === 0) return a.where?.startsWith('at ') ? ' (boarding)' : ' (arriving)'
  return ` (${a.stopsAway} stop${a.stopsAway === 1 ? '' : 's'})`
}

/** One line: the next two trains per stop, the first with how many stops out it is. */
export function statusLine(boards: Board[]): string {
  const parts = boards.map(({ watch, arrivals }) => {
    if (arrivals.length === 0) return `${watch.label}: none`
    const [first, second] = arrivals
    return `${watch.label} ${mins(first!)}${away(first!)}${second ? `, ${mins(second)}` : ''}`
  })
  return `🚋 ${parts.join(' · ')}`
}

/**
 * Trains that have come within `withinMinutes` of their stop since the last
 * check: one message per train, never repeated. `alerted` is the memory of
 * which trains were announced; ids of trains no longer predicted are dropped.
 */
export function dueAlerts(boards: Board[], withinMinutes: number, alerted: Set<string>): string[] {
  const live = new Set<string>()
  const out: string[] = []
  for (const { watch, arrivals } of boards) {
    for (const a of arrivals) {
      live.add(a.id)
      if (a.minutes > withinMinutes || alerted.has(a.id)) continue
      alerted.add(a.id)
      const when = a.minutes === 0 ? 'now' : `in ${a.minutes} min`
      const where = a.stopsAway === undefined ? '' : ` (${a.stopsAway} stop${a.stopsAway === 1 ? '' : 's'} away)`
      out.push(`${watch.label}: train ${when}${where}`)
    }
  }
  for (const id of alerted) if (!live.has(id)) alerted.delete(id)
  return out
}

/** The /greenline answer: the next three trains per stop, with where each is. */
export function detail(boards: Board[]): string {
  return boards
    .map(({ watch, arrivals }) => {
      const head = `${watch.label} (Green Line C)`
      if (arrivals.length === 0) return `${head}\n  no trains predicted`
      const rows = arrivals.slice(0, 3).map(a => {
        const bits = [a.minutes === 0 ? 'now' : `${a.minutes} min`]
        if (a.stopsAway !== undefined) bits.push(`${a.stopsAway} stop${a.stopsAway === 1 ? '' : 's'} away`)
        if (a.where) bits.push(a.where)
        if (a.status) bits.push(a.status)
        return `  ${bits.join(' · ')}`
      })
      return [head, ...rows].join('\n')
    })
    .join('\n\n')
}
