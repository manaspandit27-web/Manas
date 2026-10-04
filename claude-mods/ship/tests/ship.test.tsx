import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { parseConfig, parseWorktrees, summarize } from '../hooks/git'

const PORCELAIN = `worktree /code/sim
HEAD 1111111
branch refs/heads/main

worktree /code/sim-wt/game-ui
HEAD 2222222
branch refs/heads/game-ui

worktree /code/sim-wt/old
HEAD 3333333
detached
prunable gitdir file points to non-existent location
`

test('worktrees parse with branch, detached and prunable', () => {
  const list = parseWorktrees(PORCELAIN)
  expect(list.map(w => w.branch)).toEqual(['main', 'game-ui', null])
  expect(list[2]?.isPrunable).toBe(true)
})

test('config fills defaults and takes strings or lists', () => {
  const cfg = parseConfig('{"test": "npm test", "rebuild": ["make sandbox"]}')
  expect(cfg).toEqual({
    main: 'main',
    remote: 'origin',
    test: ['npm test'],
    rebuild: ['make sandbox'],
    pushTo: 'main',
  })
  expect(parseConfig(undefined)).toBeUndefined()
})

test('summary names unpushed and uncommitted work', () => {
  expect(
    summarize([
      { name: 'main', isCurrent: true, unpushed: 3, dirty: 0 },
      { name: 'game-ui', isCurrent: false, unpushed: 5, dirty: 2 },
      { name: 'old', isCurrent: false, unpushed: 0, dirty: 0 },
    ]),
  ).toBe('⇡ unpushed: main* +3, game-ui +5  ·  ✎ uncommitted: game-ui 2')
  expect(summarize([{ name: 'main', isCurrent: true, unpushed: 0, dirty: 0 }])).toBe('')
})

const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 6, bodyColumns: 100, scroll: { offset: 0, bodyRows: 5 }, view: {} },
} as const

function fakeRepo(on: On, branch: string) {
  mock.clock(on)
  mock.store(on)
  on('session.cwd', () => ({ value: '/code/sim' }))
  on('fs.read', () => ({ deny: 'ENOENT' }))
  on('process.run', (_$, e) => {
    const args = e.argv.slice(1).join(' ')
    const out = (stdout: string) => ({
      value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
    })
    if (args === 'rev-parse --show-toplevel') return out('/code/sim\n')
    if (args === 'branch --show-current') return out(`${branch}\n`)
    if (args === 'worktree list --porcelain') return out(PORCELAIN)
    if (args === 'remote') return out('origin\n')
    if (args === 'status --porcelain') return out(e.init?.cwd === '/code/sim-wt/game-ui' ? ' M a.ts\n' : '')
    if (args.startsWith('rev-list --count HEAD --not --remotes')) return out(e.init?.cwd === '/code/sim' ? '2\n' : '0\n')
    return out('')
  })
}

test('the band shows unpushed and uncommitted work', async ($, on) => {
  fakeRepo(on, 'main')
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('ui.render', { component: 'AbovePrompt' }, ($$, e) => {
    const { Box } = $$.ui.resolve(e)
    return <Box />
  })
  await $.session.start({ cwd: '/code/sim', surface: 'terminal', isInteractive: true })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ship', surface, ...BAND })
    expect((await ui.find({ type: 'Text', text: /unpushed: main\* \+2/ }))?.text).toContain('uncommitted: game-ui 1')
    expect(await ui.find({ type: 'Button', key: 'ship' })).toBeDefined()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ plugin: 'ship', surface: 'terminal', ...BAND })
  await ui.press({ key: 'hide' })
  expect(await ui.find({ type: 'Text', text: /unpushed/ })).toBeUndefined()
  await ui.unmount()
})
