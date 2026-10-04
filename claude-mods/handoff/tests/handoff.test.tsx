import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import type { HandoffEntry } from '../types'
import { cleanTitle, goalOf, pickNumber, recentFor, slug } from '../hooks/notes'

const NOW = Date.parse('2026-10-04T15:00:00Z')
const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 120, scroll: { offset: 0, bodyRows: 5 }, view: {} },
} as const
const OLD: HandoffEntry = {
  sessionId: 'old-session-1',
  title: 'Economic simulator review',
  project: '/code/sim',
  cwd: '/code/sim',
  path: '/home/m/.claude/handoffs/sim-x/old.md',
  at: NOW - 2 * 3_600_000,
  lastAt: NOW - 2 * 3_600_000,
}
const OLD_NOTE = '# Handoff: Economic simulator review\n\n## Goal\nValidate the sim against SEC data.\n## State\n3 corrections done.'

test('helpers', () => {
  expect(slug('Economic simulator: review #2!')).toBe('economic-simulator-review-2')
  expect(cleanTitle('"Fix playtest roles."\nmore')).toBe('Fix playtest roles')
  expect(pickNumber('2', 3)).toBe(1)
  expect(pickNumber('none', 3)).toBeUndefined()
  expect(pickNumber('7', 3)).toBeUndefined()
  expect(goalOf(OLD_NOTE)).toBe('Validate the sim against SEC data.')
  expect(recentFor([OLD, { ...OLD, sessionId: 'me' }], '/code/sim', 'me', NOW)).toEqual([OLD])
  expect(recentFor([OLD], '/code/sim', 'me', NOW + 30 * 86_400_000)).toEqual([])
})

function world(on: On, opts: { turns?: number; classify?: string; entries?: HandoffEntry[] } = {}) {
  const clock = mock.clock(on, { now: NOW })
  mock.store(on, { entries: opts.entries ?? [] })
  mock.env(on, { HOME: '/home/m' })
  const written: Record<string, string> = {}
  const toasts: string[] = []
  on('session.cwd', () => ({ value: '/code/sim-wt/game' }))
  on('session.id', () => ({ value: 'new-session-2' }))
  on('session.turns', () => ({ value: opts.turns ?? 0 }))
  on('session.messages', () => ({ value: [{ role: 'user', text: 'Fix the playtest role assignments for Monday', toolUses: [] }] }))
  on('process.run', () => ({
    value: { exitCode: 0, stdout: '/code/sim/.git\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('fs.read', (_$, e) => (e.path === OLD.path ? { value: OLD_NOTE } : { deny: 'ENOENT' }))
  on('fs.write', (_$, e) => {
    written[e.path] = e.text
    return { value: undefined }
  })
  on('model.fork', () => ({
    value: { isAnswered: true, text: '## Goal\nShip playtest roles.', usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } },
  }))
  on('model.complete', (_$, e) => ({
    value: {
      isAnswered: true,
      text: e.prompt.startsWith('A user opened') ? (opts.classify ?? 'none') : 'Playtest role assignments',
      usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
    },
  }))
  on('ui.toast', (_$, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.log', () => ({ value: undefined }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_$, e) => ({ text: e.text, ...(e.context === undefined ? {} : { context: e.context }) }))
  on('turn.complete', (_$, e) => ({ text: e.answer }))
  on('classic.UserPromptSubmit', () => ({}))
  on('ui.render', { component: 'AbovePrompt' }, ($$, e) => {
    const { Box } = $$.ui.resolve(e)
    return <Box />
  })
  return { clock, written, toasts }
}

const submit = (text: string) =>
  ({ text, origin: { kind: 'composer' }, wait: false }) as const

test('sessions get a title from what they are about', async ($, on) => {
  world(on)
  const r = await $.classic.UserPromptSubmit({ prompt: 'Fix the playtest role assignments for Monday', source: 'user' })
  expect(r.sessionTitle).toBe('Playtest role assignments')
  const again = await $.classic.UserPromptSubmit({ prompt: 'and the docs', source: 'user' })
  expect(again.sessionTitle).toBeUndefined()
})

test('/handoff writes a note under ~/.claude/handoffs', async ($, on) => {
  const { written } = world(on)
  await $.classic.UserPromptSubmit({ prompt: 'Fix the playtest role assignments for Monday', source: 'user' })
  const r = await $.command.run({ command: 'handoff', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 100 } })
  const path = Object.keys(written)[0] ?? ''
  expect(r.text).toBe(`Handoff saved: ${path}`)
  expect(path).toMatch(/^\/home\/m\/\.claude\/handoffs\/sim-\w+\/2026-10-04-\d{4}-playtest-role-assignments-new-se\.md$/)
  expect(written[path]).toContain('# Handoff: Playtest role assignments')
  expect(written[path]).toContain('claude --resume new-session-2')
  expect(written[path]).toContain('Ship playtest roles.')
})

test('a new session offers the last handoff and attaches it on request', async ($, on) => {
  const { toasts } = world(on, { entries: [OLD] })
  await $.session.start({ cwd: '/code/sim-wt/game', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'handoff', surface: 'terminal', ...BAND })
  expect((await ui.find({ type: 'Text', text: /Economic simulator review/ }))?.text).toContain('2h ago')
  await ui.press({ key: 'attach' })
  expect(await ui.find({ type: 'Text', text: /attached to your next message/ })).toBeDefined()
  const r = await $.prompt.submit(submit('ok go'))
  expect('context' in r ? r.context?.[0] : '').toContain('Validate the sim against SEC data.')
  expect(toasts).toContain('Attached the handoff from "Economic simulator review"')
})

test('a first prompt that continues earlier work gets its handoff automatically', async ($, on) => {
  world(on, { entries: [OLD], classify: '1' })
  const r = await $.prompt.submit(submit('continue the simulator validation'))
  expect('context' in r ? r.context?.[0] : '').toContain('[handoff mod]')
})

test('an unrelated first prompt gets nothing attached', async ($, on) => {
  world(on, { entries: [OLD], classify: 'none' })
  const r = await $.prompt.submit(submit('what is the weather'))
  expect('context' in r ? r.context : undefined).toBeUndefined()
})

test('after two turns and 15 idle minutes a handoff is written', async ($, on) => {
  const { clock, written } = world(on)
  const done = { answer: 'ok', durationMs: 1000, isAborted: false, reason: 'answer' } as const
  await $.turn.complete({ ...done, turnId: 't1' })
  await clock.advance(5 * 60_000)
  expect(Object.keys(written)).toHaveLength(0)
  await $.turn.complete({ ...done, turnId: 't2' })
  await clock.advance(14 * 60_000)
  expect(Object.keys(written)).toHaveLength(0)
  await clock.advance(2 * 60_000)
  expect(Object.keys(written)).toHaveLength(1)
})
