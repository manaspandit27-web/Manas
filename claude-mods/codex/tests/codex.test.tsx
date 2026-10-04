import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const PANE = {
  component: 'Pane',
  requestId: 'codex',
  props: { title: 'Codex', isFocused: false, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

function world(on: On, opts: { dirty: boolean; codexMissing?: boolean }) {
  const clock = mock.clock(on, { now: 1_000 })
  mock.env(on, { TMPDIR: '/tmp/' })
  const seen = { argv: [] as string[][], prompts: [] as string[], stdin: [] as string[] }
  on('session.cwd', () => ({ value: '/code/sim' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('process.run', (_$, e) => {
    const args = e.argv.slice(1).join(' ')
    const out = (stdout: string, exitCode = 0) => ({
      value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
    })
    if (e.argv[0] === 'git') {
      if (args === 'branch --show-current') return out('feature\n')
      if (args === 'status --porcelain') return out(opts.dirty ? ' M sim.py\n' : '')
      if (args.startsWith('symbolic-ref')) return out('origin/main\n')
      return out('')
    }
    if (opts.codexMissing) return { deny: 'spawn codex ENOENT' }
    seen.argv.push([...e.argv])
    seen.stdin.push(e.init?.stdin ?? '')
    return out('')
  })
  on('process.spawn', async function* (_$, e) {
    seen.argv.push([...e.argv])
    yield { stream: 'stderr' as const, text: 'reading sim.py\n' }
    return { value: { code: 0, signal: null } }
  })
  on('fs.read', (_$, e) => ({ value: e.path.includes('review') ? '1. [P1] sim.py:40 divides by zero when n=0' : 'Use a queue.' }))
  on('prompt.submit', (_$, e) => {
    seen.prompts.push(e.text)
    return { text: e.text }
  })
  return { clock, seen }
}

test('/codex-review reviews uncommitted work and sends findings to Claude', async ($, on) => {
  const { clock, seen } = world(on, { dirty: true })
  const ran = await $.command.run({
    command: 'codex-review',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 160 },
  })
  expect(ran.text).toBe('Codex is reviewing uncommitted changes (see the Codex pane).')
  await clock.advance(10)
  const argv = seen.argv[0] ?? []
  expect(argv.slice(0, 4)).toEqual(['codex', 'exec', 'review', '--uncommitted'])
  expect(argv).toContain('-o')

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'codex', surface, ...PANE })
    expect((await ui.find({ type: 'Markdown' }))?.text).toContain('divides by zero')
    await ui.unmount()
  }
  const ui = await $.ui.mount({ plugin: 'codex', surface: 'terminal', ...PANE })
  await ui.press({ key: 'send' })
  expect(seen.prompts[0]).toContain('<codex-review>')
  expect(seen.prompts[0]).toContain('sim.py:40')
})

test('a clean branch is reviewed against main', async ($, on) => {
  const { clock, seen } = world(on, { dirty: false })
  const ran = await $.command.run({
    command: 'codex-review',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 160 },
  })
  expect(ran.text).toContain('feature vs main')
  await clock.advance(10)
  expect(seen.argv[0]?.slice(3, 5)).toEqual(['--base', 'main'])
})

test('Claude can ask Codex a question', async ($, on) => {
  const { seen } = world(on, { dirty: false })
  const r = await $.tool.call({ tool: 'mcp__codex__ask', question: 'Is the queue design sound?', context: 'see sim.py' } as never)
  expect(r.result).toBe('Use a queue.')
  expect(seen.argv[0]).toContain('read-only')
  expect(seen.stdin[0]).toContain('Is the queue design sound?')
})

test('a missing Codex CLI says how to install it', async ($, on) => {
  world(on, { dirty: false, codexMissing: true })
  const r = await $.tool.call({ tool: 'mcp__codex__ask', question: 'x' } as never)
  expect(String(r.result)).toContain('npm i -g @openai/codex')
})
