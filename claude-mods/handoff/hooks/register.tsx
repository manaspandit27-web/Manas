import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { HandoffEntry } from '../types'
import {
  HANDOFF_PROMPT,
  ago,
  attachment,
  cleanTitle,
  fallbackTitle,
  goalOf,
  header,
  isNameable,
  pickNumber,
  recentFor,
  shortHash,
  slug,
  stamp,
} from './notes'

type $ = EngineInterface

const offer = atom({ plugin: 'handoff', key: 'offer' } as const, null)
const more = atom({ plugin: 'handoff', key: 'more' } as const, 0)
const pending = atom({ plugin: 'handoff', key: 'pending' } as const, '')

const MAX_ENTRIES = 300

let location: 'home' | 'project' = 'home'
let idleMinutes = 31
let autoName = true

let title = ''
let isNamed = false
let isFirstPrompt = true
let turnsSince = 0
let isWriting = false
let idle: Timer | undefined

async function projectOf($: $): Promise<string> {
  const cwd = await $.session.cwd()
  const r = await $.process
    .run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd, timeoutMs: 10_000 })
    .catch(() => undefined)
  const common = r?.exitCode === 0 ? r.stdout.trim() : ''
  return common === '' ? cwd : common.replace(/[\\/]\.git[\\/]?$/, '')
}

async function entriesOf($: $): Promise<HandoffEntry[]> {
  const v = await $.store.get('entries')
  return Array.isArray(v) ? (v as HandoffEntry[]) : []
}

async function saveEntry($: $, entry: HandoffEntry) {
  const others = (await entriesOf($)).filter(e => e.sessionId !== entry.sessionId)
  const kept = [...others, entry].sort((a, b) => b.lastAt - a.lastAt).slice(0, MAX_ENTRIES)
  await $.store.set('entries', kept)
}

async function currentEntry($: $): Promise<HandoffEntry> {
  const sessionId = await $.session.id()
  const found = (await entriesOf($)).find(e => e.sessionId === sessionId)
  const now = await $.clock.now()
  const named = title !== '' ? title : found?.title ?? ''
  return {
    sessionId,
    title: named,
    project: found?.project ?? (await projectOf($)),
    cwd: found?.cwd ?? (await $.session.cwd()),
    path: found?.path ?? '',
    at: found?.at ?? 0,
    lastAt: now,
  }
}

async function dirFor($: $, project: string): Promise<string> {
  const name = project.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? 'project'
  if (location === 'project') return `${project}/.claude/handoffs`
  const home = (await $.env.get('HOME')) ?? (await $.env.get('USERPROFILE')) ?? '.'
  return `${home}/.claude/handoffs/${slug(name, 30)}-${shortHash(project)}`
}

async function writeHandoff($: $, reason: string): Promise<string | undefined> {
  if (isWriting) return undefined
  isWriting = true
  try {
    const r = await $.model.fork({ prompt: HANDOFF_PROMPT })
    if (!r.isAnswered) {
      $.ui.log(`handoff not written (${r.reason})`, { to: 'debug' })
      return undefined
    }
    const now = await $.clock.now()
    const entry = await currentEntry($)
    if (entry.title === '') {
      const first = (await $.session.messages()).find(m => m.role === 'user')
      entry.title = fallbackTitle(first?.text ?? 'session')
    }
    if (entry.path === '') {
      entry.path = `${await dirFor($, entry.project)}/${stamp(now)}-${slug(entry.title)}-${entry.sessionId.slice(0, 6)}.md`
    }
    await $.fs.write(entry.path, `${header(entry, now, reason)}${r.text.trim()}\n`)
    await saveEntry($, { ...entry, at: now, lastAt: now })
    turnsSince = 0
    return entry.path
  } finally {
    isWriting = false
  }
}

async function nameFrom($: $, prompt: string): Promise<string | undefined> {
  const said = (await $.session.messages())
    .filter(m => m.role === 'user')
    .map(m => m.text)
    .concat(prompt)
    .join('\n')
  if (!isNameable(said)) return undefined
  const r = await $.model.complete({
    model: 'haiku',
    system: 'You name coding sessions. Reply with a title of 3 to 6 words in sentence case, no quotes, no punctuation at the end.',
    prompt: `Name the session these user messages belong to:\n\n${said.slice(0, 3000)}`,
    maxTokens: 30,
    timeoutMs: 8000,
  })
  return r.isAnswered ? (cleanTitle(r.text) ?? fallbackTitle(said)) : fallbackTitle(said)
}

/** On the session's first prompt: whether it continues one of the project's recent handoffs. */
async function matchHandoff($: $, prompt: string): Promise<HandoffEntry | undefined> {
  const now = await $.clock.now()
  const recent = recentFor(await entriesOf($), await projectOf($), await $.session.id(), now).slice(0, 4)
  if (recent.length === 0) return undefined
  const lines: string[] = []
  for (const [i, e] of recent.entries()) {
    const note = await $.fs.read(e.path).catch(() => '')
    lines.push(`${i + 1}. "${e.title}" (${ago(now - e.at)}): ${goalOf(typeof note === 'string' ? note : '')}`)
  }
  const r = await $.model.complete({
    model: 'haiku',
    prompt: `A user opened a new coding session on a project and typed the message below. Here are handoff notes from earlier sessions on the same project. Which session does the message continue? Reply with its number only, or "none" if the message starts something else.\n\nMessage: """${prompt.slice(0, 1500)}"""\n\n${lines.join('\n')}`,
    maxTokens: 10,
    timeoutMs: 6000,
  })
  if (!r.isAnswered) return undefined
  const i = pickNumber(r.text, recent.length)
  return i === undefined ? undefined : recent[i]
}

async function offerOnStart($: $) {
  if ((await $.session.turns()) > 0) return
  const now = await $.clock.now()
  const recent = recentFor(await entriesOf($), await projectOf($), await $.session.id(), now)
  await update($, offer, () => recent[0] ?? null)
  await update($, more, () => Math.max(0, recent.length - 1))
}

async function listHandoffs($: $, args: string): Promise<string> {
  const now = await $.clock.now()
  const recent = recentFor(await entriesOf($), await projectOf($), await $.session.id(), now, 30 * 86_400_000).slice(0, 9)
  if (recent.length === 0) return 'No handoffs for this project in the last 30 days.'
  const pick = /^\d+$/.test(args) ? recent[Number(args) - 1] : undefined
  if (pick !== undefined) {
    await update($, pending, () => pick.path)
    return `Attached "${pick.title}" to your next message.`
  }
  const rows = recent.map(
    (e, i) => `${i + 1}. ${e.title} · ${ago(now - e.at)}\n   ${e.path}\n   claude --resume ${e.sessionId}`,
  )
  return `${rows.join('\n')}\n\n/handoffs <n> attaches one to your next message.`
}

async function scheduleIdle($: $) {
  idle?.cancel()
  idle = undefined
  if (idleMinutes <= 0) return
  idle = $.clock.after(idleMinutes * 60_000, () => {
    if (turnsSince >= 2) void writeHandoff($, 'idle').catch(() => undefined)
  })
}

async function touch($: $) {
  const entry = await currentEntry($)
  await saveEntry($, entry)
}

export const register: Register = (on, options) => {
  location = options.location === 'project' ? 'project' : 'home'
  idleMinutes = Number(options.idleMinutes ?? 31)
  autoName = options.autoName !== false

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'handoff',
      description: 'Write a handoff note for this session now',
    })
    await $.command.register({
      name: 'handoffs',
      description: "List this project's recent handoffs; /handoffs <n> attaches one to your next message",
      argumentHint: '[n]',
    })
    if (e.isInteractive) await offerOnStart($)
    return started
  })

  on('classic.UserPromptSubmit', async ($, e, next) => {
    const r = await next(e)
    if ((e.session_title ?? '') !== '') title = e.session_title ?? title
    const isPerson = e.source === undefined || e.source === 'user' || e.source === 'sdk'
    if (!autoName || isNamed || !isPerson || (e.session_title ?? '') !== '') return r
    const named = await nameFrom($, e.prompt).catch(() => undefined)
    if (named === undefined) return r
    isNamed = true
    title = named
    return { ...r, sessionTitle: named }
  })

  on('prompt.submit', async ($, e, next) => {
    idle?.cancel()
    idle = undefined
    if (e.origin.kind === 'plugin' || e.origin.kind === 'task-notification') return next(e)
    const wasFirst = isFirstPrompt
    isFirstPrompt = false
    await update($, offer, () => null)

    const now = await $.clock.now()
    const attached = await read($, pending)
    let entry: HandoffEntry | undefined
    if (attached !== '') {
      entry = (await entriesOf($)).find(x => x.path === attached)
      await update($, pending, () => '')
    } else if (wasFirst) {
      entry = await matchHandoff($, e.text).catch(() => undefined)
    }
    if (entry === undefined) return next(e)
    const note = await $.fs.read(entry.path).catch(() => undefined)
    if (typeof note !== 'string') return next(e)
    $.ui.toast(`Attached the handoff from "${entry.title}"`)
    return next({ ...e, context: [...(e.context ?? []), attachment(entry, note, now)] })
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId !== undefined) return done
    turnsSince += 1
    await touch($)
    await scheduleIdle($)
    return done
  })

  on('session.compact', async ($, e, next) => {
    if ((e.trigger === 'auto' || e.trigger === 'manual') && e.agentId === undefined && turnsSince >= 1) {
      await writeHandoff($, 'compaction').catch(() => undefined)
    }
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    idle?.cancel()
    if (turnsSince >= 1) await writeHandoff($, e.reason === 'clear' ? 'clear' : 'exit').catch(() => undefined)
    return next(e)
  })

  on('command.run', { command: 'handoff' }, async ($, e) => {
    const path = await writeHandoff($, e.args.trim() === 'limit' ? 'limit' : 'request')
    return { text: path === undefined ? 'No handoff written: nothing to hand off yet, or the model call failed.' : `Handoff saved: ${path}` }
  })

  on('command.run', { command: 'handoffs' }, async ($, e) => ({ text: await listHandoffs($, e.args.trim()) }))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const below = await next(e)
    if (e.props.hasSurvey) return below
    const last = await read($, offer)
    const attached = await read($, pending)
    if (last === null && attached === '') return below
    const { Box, Button, Text } = $.ui.resolve(e)
    const now = await $.clock.now()
    const extra = await read($, more)

    if (attached !== '') {
      return (
        <Box flexDirection="column">
          <Box flexDirection="row" gap={1}>
            <Text color="cyan">↩ A handoff is attached to your next message.</Text>
            <Button key="remove" label="Remove" onPress={() => update($, pending, () => '')} />
          </Box>
          {below}
        </Box>
      )
    }
    if (last === null) return below
    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          <Text color="cyan" wrap="truncate-end">
            ↩ Last session here: "{last.title}" · {ago(now - last.at)}
            {extra > 0 ? ` (+${extra} more: /handoffs)` : ''}
          </Text>
          <Button
            key="attach"
            label="Pick it up"
            variant="primary"
            onPress={async () => {
              await update($, pending, () => last.path)
              await update($, offer, () => null)
            }}
          />
          <Button
            key="copy"
            label="Copy resume"
            onPress={press => void $.ui.copy({ text: `claude --resume ${last.sessionId}`, surface: press.surface }).catch(() => undefined)}
          />
          <Button key="dismiss" label="Dismiss" onPress={() => update($, offer, () => null)} />
        </Box>
        {below}
      </Box>
    )
  })
}
