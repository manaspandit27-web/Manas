import { atom, read, update } from 'claude-code'
import type { EngineInterface, ProcessRunResult, Register } from 'claude-code'

import type { CodexRun } from '../types'

type $ = EngineInterface

const PANE = 'codex'
const IDLE: CodexRun = { status: 'idle', scope: '', startedAt: 0, log: '', text: '' }
const run = atom({ plugin: 'codex', key: 'run' } as const, IDLE)

const NOT_FOUND =
  'Codex CLI not found. Install it with `npm i -g @openai/codex`, run `codex login`, or set this mod\'s "Codex command" in /config.'

const ASK_PROMPT = `You are a second opinion for another coding agent (Claude) working in this repository.
Answer its question below. Read whatever code you need, but do not modify any files.
Be direct and specific: cite file:line, say how confident you are, and point out anything Claude seems to be missing or getting wrong.`

let codexCommand = 'codex'
let codexModel = ''
let child: AsyncGenerator<unknown, unknown> | undefined

const tailLines = (text: string, n: number): string => text.split('\n').slice(-n).join('\n')

async function git($: $, args: readonly string[], cwd: string): Promise<ProcessRunResult> {
  return $.process.run(['git', ...args], { cwd, timeoutMs: 30_000 })
}

async function tempFile($: $, name: string): Promise<string> {
  const dir = ((await $.env.get('TMPDIR')) ?? '/tmp').replace(/\/+$/, '')
  return `${dir}/claude-codex-${name}-${await $.clock.now()}-${Math.random().toString(36).slice(2, 8)}.md`
}

/** What to review: the argument if given, else uncommitted work, else this branch against the default branch, else HEAD. */
async function scopeOf($: $, args: string, cwd: string): Promise<{ flags: string[]; label: string }> {
  const branch = (await git($, ['branch', '--show-current'], cwd)).stdout.trim() || 'HEAD'
  if (/^(--)?uncommitted$/.test(args)) return { flags: ['--uncommitted'], label: 'uncommitted changes' }
  if (/^[0-9a-f]{7,40}$/i.test(args)) return { flags: ['--commit', args], label: `commit ${args}` }
  if (args !== '') return { flags: ['--base', args], label: `${branch} vs ${args}` }

  const dirty = (await git($, ['status', '--porcelain'], cwd)).stdout.trim() !== ''
  if (dirty) return { flags: ['--uncommitted'], label: 'uncommitted changes' }
  const head = (await git($, ['symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], cwd)).stdout.trim()
  const base = head.replace(/^origin\//, '') || 'main'
  if (branch !== base) return { flags: ['--base', base], label: `${branch} vs ${base}` }
  return { flags: ['--commit', 'HEAD'], label: 'the last commit' }
}

async function review($: $, flags: readonly string[], label: string, cwd: string) {
  const out = await tempFile($, 'review')
  const model = codexModel === '' ? [] : ['-m', codexModel]
  const argv = [codexCommand, 'exec', 'review', ...flags, ...model, '-o', out]
  const startedAt = await $.clock.now()
  await update($, run, () => ({ status: 'running', scope: label, startedAt, log: '', text: '' }))
  $.ui.status(`codex: reviewing ${label}`)

  let log = ''
  try {
    const stream = $.process.spawn({ argv, cwd })
    child = stream
    for await (const piece of stream) {
      log = tailLines(log + piece.text, 60)
      await update($, run, r => ({ ...r, log }))
    }
    const ended = await stream.result
    const text = await $.fs.read(out).catch(() => undefined)
    if (ended.code === 0 && typeof text === 'string' && text.trim() !== '') {
      await update($, run, (r): CodexRun => ({ ...r, status: 'done', text: text.trim() }))
      $.ui.toast(`Codex review of ${label} is ready`, { timeoutMs: 8000 })
    } else {
      const why = ended.signal !== null ? `stopped (${ended.signal})` : `exited ${String(ended.code)}`
      await update($, run, (r): CodexRun => ({ ...r, status: 'failed', text: `Codex ${why}.\n\n${tailLines(log, 15)}` }))
    }
  } catch (err) {
    const text = /ENOENT|not found|cannot start/i.test(String(err)) ? NOT_FOUND : `Codex did not run: ${String(err)}`
    await update($, run, (r): CodexRun => ({ ...r, status: 'failed', text }))
  } finally {
    child = undefined
    $.ui.status(undefined)
  }
}

async function ask($: $, question: string, context: string): Promise<string> {
  const out = await tempFile($, 'ask')
  const model = codexModel === '' ? [] : ['-m', codexModel]
  const prompt = `${ASK_PROMPT}\n\nQuestion:\n${question}${context === '' ? '' : `\n\nContext from Claude:\n${context}`}`
  const argv = [codexCommand, 'exec', '-s', 'read-only', '--skip-git-repo-check', '--color', 'never', ...model, '-o', out, '-']
  $.ui.status('codex: thinking…')
  try {
    const r = await $.process.run(argv, { stdin: prompt, timeoutMs: 600_000 })
    const text = await $.fs.read(out).catch(() => undefined)
    if (r.exitCode === 0 && typeof text === 'string' && text.trim() !== '') return text.trim()
    return `Codex exited ${r.exitCode} without an answer.\n${tailLines(`${r.stdout}\n${r.stderr}`, 15)}`
  } catch (err) {
    return /ENOENT|not found|cannot start/i.test(String(err)) ? NOT_FOUND : `Codex did not answer: ${String(err)}`
  } finally {
    $.ui.status(undefined)
  }
}

async function sendToClaude($: $) {
  const r = await read($, run)
  if (r.status !== 'done') return
  await $.prompt.submit({
    text: `Codex reviewed ${r.scope}. Check each finding against the code yourself: fix the ones that are real, and tell me which you rejected and why.\n\n<codex-review>\n${r.text}\n</codex-review>`,
  })
}

export const register: Register = (on, options) => {
  codexCommand = String(options.command ?? 'codex') || 'codex'
  codexModel = String(options.model ?? '')

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'codex-review',
      description: 'Have Codex review your changes in a side pane (default: uncommitted, else branch vs main)',
      argumentHint: '[uncommitted|<base-branch>|<sha>]',
    })
    await $.tool.register({
      name: 'ask',
      description:
        'Ask OpenAI Codex, a separate coding agent, for a second opinion on this repository: a review of an approach, a design question, a debugging hypothesis. Codex reads the repo itself (read-only) and answers in prose. Slow (one to several minutes), so use it for consequential decisions or when stuck, not for lookups.',
      inputSchema: {
        type: 'object',
        properties: {
          question: { type: 'string', description: 'What to ask Codex, self-contained' },
          context: { type: 'string', description: 'What you have tried or found so far, and the files involved' },
        },
        required: ['question'],
      },
    })
    return started
  })

  on('command.run', { command: 'codex-review' }, async ($, e) => {
    const now = await read($, run)
    if (now.status === 'running') {
      await $.ui.open({ id: PANE, title: 'Codex' })
      return { text: `Codex is still reviewing ${now.scope}.` }
    }
    const cwd = await $.session.cwd()
    const scope = await scopeOf($, e.args.trim(), cwd)
    await update($, run, () => ({ ...IDLE, status: 'running', scope: scope.label }))
    await $.ui.open({ id: PANE, title: 'Codex' })
    $.clock.after(0, () => void review($, scope.flags, scope.label, cwd).catch(() => undefined))
    return { text: `Codex is reviewing ${scope.label} (see the Codex pane).` }
  })

  on('tool.call', { tool: 'mcp__codex__ask' }, async ($, e) => {
    const input = e as unknown as { question?: unknown; context?: unknown }
    const question = typeof input.question === 'string' ? input.question : ''
    if (question.trim() === '') return { deny: 'ask needs a question.' }
    const context = typeof input.context === 'string' ? input.context : ''
    return { result: await ask($, question, context) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const r = await read($, run)
    const { Box, Button, Markdown, Text } = $.ui.resolve(e)
    const room = Math.max(4, (e.viewport?.rows ?? 24) - 8)

    if (r.status === 'idle') {
      return <Text dimColor>Run /codex-review to have Codex review your changes.</Text>
    }
    if (r.status === 'running') {
      return (
        <Box flexDirection="column">
          <Text bold>Reviewing {r.scope}…</Text>
          <Text dimColor wrap="truncate-end">
            {tailLines(r.log, room) || 'starting codex'}
          </Text>
          <Box flexDirection="row" gap={1}>
            <Button key="cancel" label="Cancel" onPress={() => void child?.return(undefined).catch(() => undefined)} />
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="column">
        <Text bold color={r.status === 'done' ? 'green' : 'red'}>
          {r.status === 'done' ? `Codex on ${r.scope}` : `Codex review of ${r.scope} failed`}
        </Text>
        <Markdown text={r.text} />
        <Box flexDirection="row" gap={1}>
          {r.status === 'done' && (
            <Button key="send" label="Send to Claude" variant="primary" onPress={() => void sendToClaude($).catch(() => undefined)} />
          )}
          {r.status === 'done' && (
            <Button key="copy" label="Copy" onPress={press => void $.ui.copy({ text: r.text, surface: press.surface }).catch(() => undefined)} />
          )}
          <Button key="close" label="Close" role="dismiss" onPress={() => void $.ui.close({ id: PANE }).catch(() => undefined)} />
        </Box>
      </Box>
    )
  })
}
