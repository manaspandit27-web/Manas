import { atom, read, update } from 'claude-code'
import type { EngineInterface, ProcessRunResult, Register } from 'claude-code'

import type { ShipTree } from '../types'
import { basename, parseConfig, parseWorktrees, summarize, tail, type ShipConfig } from './git'

type $ = EngineInterface

const trees = atom({ plugin: 'ship', key: 'trees' } as const, [])
const hiddenFor = atom({ plugin: 'ship', key: 'hiddenFor' } as const, '')
const running = atom({ plugin: 'ship', key: 'running' } as const, '')

const SETUP_PROMPT = `Ship this repo's work the way I usually do it:
1. Run the project's tests/checks; stop and tell me if anything fails.
2. Fast-forward main to this branch and push it (no rebase, no force-push; if main has diverged, stop and ask).
3. Run whatever rebuilds the sandbox or deploys this project, if there is such a step.
4. Give me a one-line receipt: commits shipped, new main sha, test result, rebuild result.
Then save what you used as .claude/ship.json so /ship can do it directly next time:
{"main": "main", "remote": "origin", "test": ["<command>"], "rebuild": ["<command>"], "pushTo": "main"}
("pushTo": "branch" if this repo should only push its branch). Ask me before pushing if anything is unclear.`

let isScanning = false

async function git($: $, args: readonly string[], cwd: string): Promise<ProcessRunResult> {
  return $.process.run(['git', ...args], { cwd, timeoutMs: 30_000 })
}

async function countOf($: $, top: string, range: string): Promise<number | undefined> {
  const r = await git($, ['rev-list', '--count', range], top)
  const n = Number(r.stdout.trim())
  return r.exitCode === 0 && !Number.isNaN(n) ? n : undefined
}

async function sh($: $, command: string, cwd: string): Promise<ProcessRunResult> {
  return $.process.run(['sh', '-c', command], { cwd, timeoutMs: 600_000 }).catch((err: unknown) => ({
    exitCode: -1,
    stdout: '',
    stderr: `did not finish: ${String(err)} (steps are capped at 10 minutes)`,
    isStdoutTruncated: false,
    isStderrTruncated: false,
  }))
}

async function topOf($: $): Promise<string | undefined> {
  const r = await git($, ['rev-parse', '--show-toplevel'], await $.session.cwd())
  return r.exitCode === 0 ? r.stdout.trim() : undefined
}

async function scan($: $): Promise<ShipTree[]> {
  const top = await topOf($)
  if (top === undefined) return []
  const list = await git($, ['worktree', 'list', '--porcelain'], top)
  if (list.exitCode !== 0) return []
  const hasRemote = (await git($, ['remote'], top)).stdout.trim() !== ''
  const out: ShipTree[] = []
  for (const wt of parseWorktrees(list.stdout)) {
    if (wt.isBare || wt.isPrunable) continue
    const status = await git($, ['status', '--porcelain'], wt.path)
    if (status.exitCode !== 0) continue
    const dirty = status.stdout.split('\n').filter(Boolean).length
    let unpushed = 0
    if (hasRemote) {
      const r = await git($, ['rev-list', '--count', 'HEAD', '--not', '--remotes'], wt.path)
      unpushed = r.exitCode === 0 ? Number(r.stdout.trim()) || 0 : 0
    }
    out.push({ path: wt.path, name: wt.branch ?? basename(wt.path), isCurrent: wt.path === top, unpushed, dirty })
  }
  return out
}

async function refresh($: $) {
  if (isScanning) return
  isScanning = true
  try {
    const found = await scan($)
    await update($, trees, () => found)
  } finally {
    isScanning = false
  }
}

async function configOf($: $, top: string): Promise<ShipConfig | undefined> {
  const text = await $.fs.read(`${top}/.claude/ship.json`).catch(() => undefined)
  return parseConfig(typeof text === 'string' ? text : undefined)
}

async function step($: $, what: string) {
  await update($, running, () => what)
  $.ui.status(what === '' ? undefined : `ship: ${what}`)
}

async function updateLocalMain($: $, top: string, cfg: ShipConfig, branch: string | null): Promise<string> {
  if (branch === cfg.main) return ''
  const list = await git($, ['worktree', 'list', '--porcelain'], top)
  const holder = parseWorktrees(list.stdout).find(w => w.branch === cfg.main)
  if (holder === undefined) {
    const r = await git($, ['branch', '-f', cfg.main, `${cfg.remote}/${cfg.main}`], top)
    return r.exitCode === 0 ? '' : ` (local ${cfg.main} not moved: ${r.stderr.trim()})`
  }
  const status = await git($, ['status', '--porcelain'], holder.path)
  if (status.stdout.trim() !== '') return ` (local ${cfg.main} worktree has uncommitted changes; left it alone)`
  const r = await git($, ['merge', '--ff-only', `${cfg.remote}/${cfg.main}`], holder.path)
  return r.exitCode === 0 ? '' : ` (local ${cfg.main} not fast-forwarded: ${r.stderr.trim()})`
}

async function ship($: $, args: string): Promise<string> {
  const top = await topOf($)
  if (top === undefined) return 'Not inside a git repository.'

  if (args === 'status') {
    await refresh($)
    const list = await read($, trees)
    if (list.length === 0) return 'No worktrees found.'
    return list
      .map(t => `${t.isCurrent ? '*' : ' '} ${t.name.padEnd(28)} unpushed ${String(t.unpushed).padStart(3)}  uncommitted ${String(t.dirty).padStart(3)}  ${t.path}`)
      .join('\n')
  }

  let cfg: ShipConfig | undefined
  try {
    cfg = await configOf($, top)
  } catch (err) {
    return `.claude/ship.json does not parse: ${String(err)}`
  }
  if (cfg === undefined) {
    void $.prompt.submit({ text: SETUP_PROMPT }).catch(() => undefined)
    return 'No .claude/ship.json in this repo yet: asked Claude to run the ship routine and save it for next time.'
  }

  const branch = (await git($, ['branch', '--show-current'], top)).stdout.trim() || null
  if (branch === null) return 'HEAD is detached: check out a branch, then /ship.'
  const dirty = (await git($, ['status', '--porcelain'], top)).stdout.split('\n').filter(Boolean).length
  if (dirty > 0) return `${dirty} uncommitted file(s) in ${basename(top)}: commit or stash them first, then /ship.`

  await step($, `fetching ${cfg.remote}`)
  try {
    const fetched = await git($, ['fetch', cfg.remote, cfg.main], top)
    if (fetched.exitCode !== 0) return `✗ git fetch failed:\n${tail(fetched.stderr)}`
    const base = `${cfg.remote}/${cfg.main}`
    const target = cfg.pushTo === 'main' ? cfg.main : branch
    let ahead = (await countOf($, top, `${base}..HEAD`)) ?? 0
    if (cfg.pushTo === 'branch') ahead = (await countOf($, top, `${cfg.remote}/${branch}..HEAD`)) ?? ahead

    if (cfg.pushTo === 'main') {
      const isAncestor = (await git($, ['merge-base', '--is-ancestor', base, 'HEAD'], top)).exitCode === 0
      if (!isAncestor) {
        const behind = (await git($, ['rev-list', '--count', `HEAD..${base}`], top)).stdout.trim()
        return `✗ ${base} has ${behind} commit(s) ${branch} lacks: merge it in first (git merge ${base}), then /ship.`
      }
      if (ahead === 0) return `Nothing to ship: ${base} already has everything on ${branch}.`
    }

    if (!/\b(yes|-y)\b/.test(args)) {
      const question = `Ship ${ahead} commit(s) from ${branch} to ${cfg.remote}/${target}${cfg.test.length > 0 ? ' after the tests' : ''}?`
      const answer = await $.ui.ask(question, ['Ship', 'Cancel']).catch(() => 'Cancel')
      if (answer !== 'Ship') return 'Not shipped. (/ship yes skips the question.)'
    }

    let testNote = 'no tests configured'
    for (const command of cfg.test) {
      await step($, `testing: ${command}`)
      const r = await sh($, command, top)
      if (r.exitCode !== 0) {
        return `✗ Tests failed, nothing pushed: ${command} (exit ${r.exitCode})\n${tail(`${r.stdout}\n${r.stderr}`)}`
      }
      testNote = tail(r.stdout || r.stderr, 1) || 'passed'
    }

    await step($, `pushing to ${cfg.remote}/${target}`)
    let note = ''
    if (cfg.pushTo === 'main') {
      if (branch !== cfg.main) {
        const own = await git($, ['push', '-u', cfg.remote, branch], top)
        if (own.exitCode !== 0) note += ` (branch push failed: ${tail(own.stderr, 1)})`
      }
      const pushed = await git($, ['push', cfg.remote, `HEAD:${cfg.main}`], top)
      if (pushed.exitCode !== 0) return `✗ Push to ${base} failed:\n${tail(pushed.stderr)}`
      note += await updateLocalMain($, top, cfg, branch)
    } else {
      const pushed = await git($, ['push', '-u', cfg.remote, branch], top)
      if (pushed.exitCode !== 0) return `✗ Push of ${branch} failed:\n${tail(pushed.stderr)}`
    }
    const sha = (await git($, ['rev-parse', '--short', 'HEAD'], top)).stdout.trim()

    let rebuildNote = ''
    for (const command of cfg.rebuild) {
      await step($, `rebuilding: ${command}`)
      const r = await sh($, command, top)
      if (r.exitCode !== 0) {
        rebuildNote = ` · rebuild ✗ ${command} (exit ${r.exitCode})\n${tail(`${r.stdout}\n${r.stderr}`)}`
        break
      }
      rebuildNote = ' · rebuild ✓'
    }

    const receipt = `✓ Shipped ${ahead} commit(s) ${branch} → ${cfg.remote}/${target} (${sha}) · tests ✓ ${testNote}${rebuildNote}${note}`
    const kept = await $.store.get('receipts')
    const receipts = Array.isArray(kept) ? kept : []
    await $.store.set('receipts', [...receipts, { at: await $.clock.now(), repo: top, receipt }].slice(-50))
    return receipt
  } finally {
    await step($, '')
    await refresh($)
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'ship',
      description: 'Test, fast-forward main, push and rebuild (from .claude/ship.json); /ship status lists worktrees',
      argumentHint: '[status|yes]',
    })
    await refresh($)
    $.clock.every(120_000, () => void refresh($))
    return started
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined) await refresh($)
    return done
  })

  on('command.run', { command: 'ship' }, async ($, e) => ({ text: await ship($, e.args.trim()) }))

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    if (/\bgit\b/.test(e.command)) $.clock.after(500, () => void refresh($))
    return ran
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const below = await next(e)
    if (e.props.hasSurvey) return below
    const list = await read($, trees)
    const now = await read($, running)
    const line = summarize(list)
    const hidden = await read($, hiddenFor)
    if (now === '' && (line === '' || hidden === line)) return below
    const { Box, Button, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          <Text color={now === '' ? 'yellow' : 'cyan'} wrap="truncate-end">
            {now === '' ? line : `ship: ${now}…`}
          </Text>
          {now === '' && (
            <Button key="ship" label="Ship" onPress={() => void $.command.run({ command: 'ship' }).catch(() => undefined)} />
          )}
          {now === '' && <Button key="hide" label="Hide" onPress={() => update($, hiddenFor, () => line)} />}
        </Box>
        {below}
      </Box>
    )
  })
}
