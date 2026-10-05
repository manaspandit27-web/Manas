import type { EngineInterface, Register } from 'claude-code'

import { API, detail, dueAlerts, loadBoards, loadLayout, statusLine } from './mbta'
import type { Board, Fetch, Layout } from './mbta'

type State = {
  configuredKey: string
  alertMinutes: number
  desktopNotify: boolean
  /** Prediction ids already announced, so each train alerts once. */
  alerted: Set<string>
  layout?: Layout
  boards: Board[]
  error?: string
}

async function refresh($: EngineInterface, state: State): Promise<void> {
  const key = state.configuredKey || ((await $.env.get('MBTA_API_KEY')) ?? '').trim()
  const headers: Record<string, string> = { accept: 'application/vnd.api+json' }
  if (key) headers['x-api-key'] = key

  const fetch: Fetch = async (path, params) => {
    const query = new URLSearchParams(params).toString()
    const res = await $.http.fetch(`${API}${path}${query ? `?${query}` : ''}`, { headers })
    if (!res.ok) {
      const hint = res.status === 403 ? ' (check api_key)' : res.status === 429 ? ' (rate limited)' : ''
      throw new Error(`MBTA API ${res.status}${hint}`)
    }
    return JSON.parse(res.text)
  }

  try {
    state.layout ??= await loadLayout(fetch)
    state.boards = await loadBoards(fetch, state.layout, await $.clock.now())
    state.error = undefined
    $.ui.status(statusLine(state.boards))
    for (const message of dueAlerts(state.boards, state.alertMinutes, state.alerted)) {
      await announce($, state, message)
    }
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
    $.ui.status(`🚋 Green Line: ${state.error}`)
  }
}

async function announce($: EngineInterface, state: State, message: string): Promise<void> {
  $.ui.toast(`🚋 ${message}`, { timeoutMs: 20000 })
  if (!state.desktopNotify) return
  // macOS notification, so it reaches you outside the terminal; elsewhere this just fails quietly
  const quoted = (text: string) => `"${text.replace(/["\\]/g, '')}"`
  try {
    await $.process.run([
      'osascript',
      '-e',
      `display notification ${quoted(message)} with title "Green Line" sound name "Glass"`,
    ])
  } catch {
    // no osascript here
  }
}

export const register: Register = (on, options) => {
  const state: State = {
    configuredKey: typeof options.api_key === 'string' ? options.api_key.trim() : '',
    alertMinutes: Number(options.alert_minutes) || 5,
    desktopNotify: options.desktop_notify !== false,
    alerted: new Set(),
    boards: [],
  }
  const refreshMs = Math.max(15, Number(options.refresh_seconds) || 30) * 1000

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'greenline',
      description: "Next Green Line C trains at Washington Square and St. Mary's Street",
    })
    void refresh($, state)
    $.clock.every(refreshMs, () => refresh($, state))
    return next(e)
  })

  on('command.run', { command: 'greenline' }, async $ => {
    await refresh($, state)
    return { text: state.error ? `Green Line: ${state.error}` : detail(state.boards) }
  })
}
